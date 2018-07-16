import gitea
import json


def main():
    with open("creds.json") as f:
        creds = json.load(f)
    client = gitea.Gitea(creds["gitea"]["url"], creds["gitea"]["token"])
    with open("hooks.json") as f:
        hooks = json.load(f)

    for repo, urls in hooks.items():
        print(repo)
        for url in urls:
            print(client.create_hook("dave", repo, url))


if __name__ == '__main__':
    main()
