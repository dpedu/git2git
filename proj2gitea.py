import gitea
from pprint import pprint
import os
from concurrent.futures import ThreadPoolExecutor
from subprocess import check_call
import json


def main():
    with open("creds.json") as f:
        creds = json.load(f)
    client = gitea.Gitea(creds["gitea"]["url"], creds["gitea"]["token"])

    projects = [i.name for i in os.scandir("tmp") if i.is_dir()]

    # import ipdb ; ipdb.set_trace()

    futures = []
    with ThreadPoolExecutor(max_workers=1) as pool:
        for project in projects:
            projdir = os.path.join("tmp", project)
            with open(projdir + ".txt") as f:
                description = f.read()

            new_repo = client.create_repo(**{"auto_init": False,
                                             "description": description,
                                             # "gitignores": "string",
                                             # "license": "string",
                                             "name": project,
                                             "private": True,
                                             # "readme": "string"
                                             })

            if "ssh_url" in new_repo:
                check_call(["git", "remote", "add", "gitea", new_repo["ssh_url"]], cwd=projdir)

            futures.append(pool.submit(check_call,
                                       ["git", "push", "gitea"],
                                       cwd=projdir))
    errors = []
    for item in futures:
        e = item.exception()
        if e:
            errors.append(e)
    print("Errors: ", len(errors))
    pprint(errors)


if __name__ == '__main__':
    main()
