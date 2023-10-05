"""
Synchronize awx Instance Groups USE permissions using dedicated Teams.
Users that are Admin or Inventory Admin of an Organization will obtain full USE on the Instance Groups listed by the Organization.
"""

import aiohttp
import asyncio

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
    default="admin,",
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
    "--ignore-certs-validation",
    default=False,
    is_flag=True,
    help="Ignore SSL certs validation.",
)
def sync(
    controller_url,
    team_prefix,
    parent_organization,
    skip_list_instance_groups,
    controller_oauth2_token,
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
            team_name = f"{team_prefix}{instance_group['name']}"
            logging.info(f"Checking status of team={team_name}")

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
            team_map[instance_group['name']] = team

    # list all organizations for each organizations, add the admins and inventory admins to the team of each Instance
    # Group referenced by the Organization
    organizations = _controller_get_all_entities(
        entity_name="organizations",
        controller_url=controller_url,
        controller_headers=controller_headers,
        validate_certs=verify_certs,
    )

    for organization in organizations:
        print(organization)

    # /!\ ensure that teams of instances groups does not contains other people than the one referenced


if __name__ == "__main__":
    sync()
