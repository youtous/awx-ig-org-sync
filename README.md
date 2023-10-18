# 🔄 AWX Sync Instance Groups Permission Based on Organizations

[![GitHub Repo stars](https://img.shields.io/github/stars/youtous/awx-ig-org-sync?label=✨%20youtous%2Fawx-ig-org-sync&style=social)](https://github.com/youtous/awx-ig-org-sync/)
[![Gitlab Repo](https://img.shields.io/badge/gitlab.com%2Fyoutous%2Fawx--ig--org--sync?label=✨%20youtous%2Fawx-ig-org-sync&style=social&logo=gitlab)](https://gitlab.com/youtous/awx-ig-org-sync/)
[![Licence](https://img.shields.io/github/license/youtous/awx-ig-org-sync)](https://github.com/youtous/awx-ig-org-sync/blob/main/LICENSE)


### Overview

This repository provides a tool to easily propagate the "use" permission of the listed instance groups within organizations to administrators or users of the organization. It addresses the need to ensure that the "use" permission for instance groups is managed by dedicated teams. This tool replicates the behavior of "use" permission for organization administrators introduced in AWX (https://github.com/ansible/awx/issues/4292), serving as a workaround until the official solution is available (https://github.com/ansible/awx/issues/14564).

### Features

- Manage "use" permission for instance groups within organizations.
- Replicate the behavior of "use" permission for organization administrators in AWX.
- Work as a temporary workaround until the official solution is available in AWX.


## Usage


1. Clone this repository:

```bash
git clone https://github.com/youtous/awx-ig-org-sync.git
```

2. Run the script, providing your controller's OAuth2 token and URL:

```bash 
python main.py --controller-oauth2-token="******************" --controller-url=https://1.1.1.2
```

You can also schedule this script to enable regular synchronization of the permissions.

## Help

This is an extract from the `--help` command:

```text
Usage: main.py [OPTIONS]

  Perform the mapping of permissions base on Organizations.

Options:
  --controller-url TEXT           Base URL of the controller.
  --team-prefix TEXT              Team prefix used to hold the permissions.
  --parent-organization TEXT      The parent organization of the teams holding
                                  permissions.
  --role-from-org-to-allow TEXT   List of Organization roles to add to the
                                  Instance Group Team with use permission,
                                  coma (,) separated.
  --skip-list-instance-groups TEXT
                                  Instance Groups list to ignore, coma (,)
                                  separated.
  --controller-oauth2-token TEXT  The awx controller oauth2 token with System
                                  Administrator privilege.
  --cleanup-use-role              If enabled, all use of instance group not
                                  managed by the team will be removed.
  --ignore-certs-validation       Ignore SSL certs validation.
  --help                          Show this message and exit.

```

## Issues

Please check our GitHub Issues and GitLab Issues for reporting any problems, requesting features, or discussing the project.

## License

This project is licensed under the MIT License.