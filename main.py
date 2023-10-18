"""
Synchronize awx Instance Groups USE permissions using dedicated Teams.
Users that are Admin or Inventory Admin of an Organization will obtain full USE on the Instance Groups listed by the Organization.
"""

import click
import logging
import os
import requests
import json
import pandas as pd

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
requests.packages.urllib3.disable_warnings()


def _controller_get_all_entities(
    entity_name,
    controller_url,
    controller_headers={},
    page_size=200,
    validate_certs=True,
):
    """
    Get all entities from the controller.
    :param entity_name:
    :param controller_url:
    :param controller_headers:
    :param page_size:
    :param validate_certs:
    :return: entities
    """

    entities = []
    url = f"{controller_url}/api/v2/{entity_name}/?page_size={page_size}"

    while True:
        logging.debug(f"Requesting GET '{url}'")
        response = requests.get(url, headers=controller_headers, verify=validate_certs)

        response.raise_for_status()
        logging.debug(f"Request content: {response.content}")
        response = response.json()

        entities.extend(response["results"])

        if response["next"] is None:
            break
        else:
            url = f"{controller_url}{response['next']}"

    return entities


def _controller_get_all_users_entity(
    entity_name,
    id,
    role,
    controller_url,
    controller_headers={},
    page_size=200,
    validate_certs=True,
):
    """
    Get all users of an entity with a specific role.
    :param entity_name:
    :param id
    :param role
    :param controller_url:
    :param controller_headers:
    :param page_size:
    :param validate_certs:
    :return: entities
    """

    entities = []
    url = f"{controller_url}/api/v2/{entity_name}/{id}/{role}/?page_size={page_size}"

    while True:
        logging.debug(f"Requesting GET '{url}'")
        response = requests.get(url, headers=controller_headers, verify=validate_certs)

        response.raise_for_status()
        logging.debug(f"Request content: {response.content}")
        response = response.json()

        entities.extend(response["results"])

        if response["next"] is None:
            break
        else:
            url = f"{controller_url}{response['next']}"

    return entities


def _controller_find_first_entity(
    entity_name, query, controller_url, controller_headers, validate_certs=True
):
    """
    Find an entity based on a query.
    :param entity_name:
    :param query:
    :param controller_url:
    :param controller_headers:
    :param validate_certs:
    :return:
    """

    url = f"{controller_url}/api/v2/{entity_name}/?page_size=1&page=1&{query}"

    logging.debug(f"Requesting GET '{url}'")
    response = requests.get(url, headers=controller_headers, verify=validate_certs)

    response.raise_for_status()
    logging.debug(f"Request content: {response.content}")
    results = response.json()
    if results["count"] == 0:
        return None
    return results["results"][0]


def _controller_create_entity(
    entity_name, data, controller_url, controller_headers, validate_certs=True
):
    """
    Create an entity.
    :param entity_name:
    :param data:
    :param controller_url:
    :param controller_headers:
    :param validate_certs:
    :return:
    """

    url = f"{controller_url}/api/v2/{entity_name}/"

    logging.debug(f"Requesting POST '{url}': {data}")
    response = requests.post(
        url, data=json.dumps(data), headers=controller_headers, verify=validate_certs
    )

    response.raise_for_status()
    return response


def _controller_delete_entity(
    entity_name, controller_url, controller_headers, validate_certs=True
):
    """
    Delete an entity.
    :param entity_name:
    :param controller_url:
    :param controller_headers:
    :param validate_certs:
    :return:
    """

    url = f"{controller_url}/api/v2/{entity_name}/"

    logging.debug(f"Requesting DELETE '{url}'")
    response = requests.delete(url, headers=controller_headers, verify=validate_certs)

    response.raise_for_status()
    return response


@click.command()
@click.option("--controller-url", help="Base URL of the controller.")
@click.option(
    "--team-prefix",
    help="Team prefix used to hold the permissions.",
    default="t-IG-USE-",
)
@click.option(
    "--parent-organization",
    help="The parent organization of the teams holding permissions.",
    default="ADMIN-AREA",
)
@click.option(
    "--role-from-org-to-allow",
    help="List of Organization roles to add to the Instance Group Team with use permission, coma (,) separated.",
    default="admins",
)
@click.option(
    "--skip-list-instance-groups",
    help="Instance Groups list to ignore, coma (,) separated.",
    default="default,controlplane",
)
@click.option(
    "--controller-oauth2-token",
    help="The awx controller oauth2 token with System Administrator privilege.",
)
@click.option(
    "--cleanup-use-role",
    default=True,
    is_flag=True,
    help="If enabled, all use of instance group not managed by the team will be removed.",
)
@click.option(
    "--ignore-certs-validation",
    default=False,
    is_flag=True,
    help="Ignore SSL certs validation.",
)
def sync(
    controller_url,
    team_prefix,
    parent_organization,
    role_from_org_to_allow,
    skip_list_instance_groups,
    controller_oauth2_token,
    cleanup_use_role,
    ignore_certs_validation,
):
    """Perform the mapping of permissions base on Organizations."""

    controller_headers = {
        "Authorization": f"Bearer {controller_oauth2_token}",
        "Content-Type": "application/json",
    }
    verify_certs = not ignore_certs_validation
    instance_groups = _controller_get_all_entities(
        entity_name="instance_groups",
        controller_url=controller_url,
        controller_headers=controller_headers,
        validate_certs=verify_certs,
    )

    logging.info(f"Found {len(instance_groups)} Instance Groups")
    skip_list_instance_group = skip_list_instance_groups.split(",")

    org = _controller_find_first_entity(
        entity_name="organizations",
        query=f"name__exact={parent_organization}",
        controller_url=controller_url,
        controller_headers=controller_headers,
        validate_certs=verify_certs,
    )
    if org is None:
        logging.error(
            f"Cannot find parent organization '{parent_organization}', please make sure it exists."
        )
        exit(1)

    # for each instance group, create if not exists a dedicated team holding the USE right for the Instance Group
    team_map = {}
    for instance_group in instance_groups:
        if instance_group["name"] not in skip_list_instance_group:
            # retrieve the USE role for the instance group
            ig_object_roles = _controller_get_all_entities(
                entity_name=f"instance_groups/{instance_group['id']}/object_roles",
                controller_url=controller_url,
                controller_headers=controller_headers,
                validate_certs=verify_certs,
            )
            ig_use_role_id = None
            for role in ig_object_roles:
                if role["name"] == "Use":
                    ig_use_role_id = role["id"]
                    break

            team_name = f"{team_prefix}{instance_group['name']}"
            logging.info(f"Checking status of team={team_name}")

            if cleanup_use_role:
                logging.info(
                    f"Removing manual USE role from users on Instance Group={instance_group['name']}"
                )
                users_with_use_role = _controller_get_all_entities(
                    entity_name=f"roles/{ig_use_role_id}/users",
                    controller_url=controller_url,
                    controller_headers=controller_headers,
                    validate_certs=verify_certs,
                )

                logging.info(
                    f"Found {len(users_with_use_role)} users with USE role on Instance Group={instance_group['name']}"
                )

                for user_to_remove_from_ig in users_with_use_role:
                    logging.info(
                        f"Removing USE role for {user_to_remove_from_ig['username']} in Instance Group={instance_group['name']}"
                    )

                    remove_result = _controller_create_entity(
                        entity_name=f"users/{user_to_remove_from_ig['id']}/roles",
                        data={"id": ig_use_role_id, disassociate: True},
                        controller_url=controller_url,
                        controller_headers=controller_headers,
                        validate_certs=verify_certs,
                    )

                    logging.info(
                        f"Removing USE role for {user_to_remove_from_ig['username']} on Instance Group={instance_group['name']} result: {remove_result}"
                    )

            team = _controller_find_first_entity(
                entity_name="teams",
                query=f"name__exact={team_name}&order_by=name&organization__name__exact={parent_organization}",
                controller_url=controller_url,
                controller_headers=controller_headers,
                validate_certs=verify_certs,
            )

            if team is None:
                logging.info(f"Creating team '{team_name}' as it appears to be missing")
                result = _controller_create_entity(
                    "teams",
                    controller_url=controller_url,
                    controller_headers=controller_headers,
                    validate_certs=verify_certs,
                    data={
                        "name": team_name,
                        "description": f"This team holds USE permission of Instance Group {instance_group['name']}",
                        "organization": org["id"],
                    },
                )
                logging.info(f"Team creation status for '{team_name}': {result}")

                team = _controller_find_first_entity(
                    entity_name="teams",
                    query=f"name__exact={team_name}&order_by=name&organization__name__exact={parent_organization}",
                    controller_url=controller_url,
                    controller_headers=controller_headers,
                    validate_certs=verify_certs,
                )

            logging.info(
                f"Ensure team={team_name} has USE role on={instance_group['name']}"
            )
            add_result = _controller_create_entity(
                entity_name=f"teams/{team['id']}/roles",
                data={"id": ig_use_role_id},
                controller_url=controller_url,
                controller_headers=controller_headers,
                validate_certs=verify_certs,
            )

            logging.info(
                f"Add team={team_name} USE role on={instance_group['name']} result: {add_result}"
            )

            team_map[team_name] = team

    # list all organizations for each organizations, add the admins and inventory admins to the team of each Instance
    # Group referenced by the Organization
    organizations = _controller_get_all_entities(
        entity_name="organizations",
        controller_url=controller_url,
        controller_headers=controller_headers,
        validate_certs=verify_certs,
    )

    role_from_org_to_allow = role_from_org_to_allow.split(",")
    allowed_users_per_ig = {}
    for organization in organizations:
        for role in role_from_org_to_allow:
            logging.info(f"Processing role={role} from org={organization}")

            org_id = organization["id"]

            role_users = _controller_get_all_entities(
                entity_name=f"organizations/{org_id}/{role}",
                controller_url=controller_url,
                controller_headers=controller_headers,
                validate_certs=verify_certs,
            )

            org_instance_groups = _controller_get_all_entities(
                entity_name=f"organizations/{org_id}/instance_groups",
                controller_url=controller_url,
                controller_headers=controller_headers,
                validate_certs=verify_certs,
            )

            # add role in each instance group
            for team_name, team_object in team_map.items():
                logging.info(
                    f"Adding {len(role_users)} {role} from {organization['name']} to team={team_name}"
                )

                if team_name not in allowed_users_per_ig:
                    allowed_users_per_ig[team_name] = {
                        "id": team_object["id"],
                        "users": [],
                    }

                allowed_users_per_ig[team_name]["users"].extend(
                    map(lambda user: user["id"], role_users)
                )

    logging.info("Applying needed changes...")

    # Perform reconcilliation of current teams state and target
    for team_name, allowed_user_list in team_map.items():
        # make sure the team has USE permission on the target Instance Group

        team_user_list = _controller_get_all_entities(
            entity_name=f"teams/{allowed_users_per_ig[team_name]['id']}/users",
            controller_url=controller_url,
            controller_headers=controller_headers,
            validate_certs=verify_certs,
        )

        target_list = set(allowed_users_per_ig[team_name]["users"])
        current_user_list_id = set()

        # retrieve Member role id for the team
        team_object_roles = _controller_get_all_entities(
            entity_name=f"teams/{allowed_users_per_ig[team_name]['id']}/object_roles",
            controller_url=controller_url,
            controller_headers=controller_headers,
            validate_certs=verify_certs,
        )
        member_role_id = None
        for role in team_object_roles:
            if role["name"] == "Member":
                member_role_id = role["id"]
                break

        # remove users not to be added
        for team_user in team_user_list:
            if team_user["id"] not in target_list:
                logging.info(
                    f"Removing {team_user['username']}#{team_user['id']} from team={team_name}"
                )
                remove_result = _controller_create_entity(
                    entity_name=f"users/{user_id}/roles",
                    data={"id": member_role_id, "disassociate": True},
                    controller_url=controller_url,
                    controller_headers=controller_headers,
                    validate_certs=verify_certs,
                )
                logging.info(
                    f"Removing user#{user_id} from team={team_name} result: {remove_result}"
                )
            else:
                current_user_list_id.add(team_user["id"])

        # ensure target list is implemented
        for user_id in target_list:
            if user_id not in current_user_list_id:
                logging.info(f"Adding missing user#{user_id} to team={team_name}")
                add_result = _controller_create_entity(
                    entity_name=f"users/{user_id}/roles",
                    data={"id": member_role_id},
                    controller_url=controller_url,
                    controller_headers=controller_headers,
                    validate_certs=verify_certs,
                )
                logging.info(
                    f"Adding user#{user_id} to team={team_name} result: {add_result}"
                )

        logging.info(f"Synchronization of Instance Groups teams completed.")


if __name__ == "__main__":
    # /api/v2/roles/{id}/users/ List Users for a Role
    sync()
