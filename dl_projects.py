from mirror import SSHAgent
from subprocess import check_call
import os
import json
import gitlab
from concurrent.futures import ThreadPoolExecutor


class DlGitlabProjects(object):
    def __init__(self, agent, gl):
        self.agent = agent
        self.gl = gl

    def run(self):
        projects = self.get_gitlab_projects()
        futures = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            for name, project in projects.items():
                # import ipdb ; ipdb.set_trace()
                if not os.path.exists(os.path.join("tmp", project.name)):
                    futures.append(pool.submit(check_call, ["git", "clone", project.ssh_url_to_repo, project.name], cwd="./tmp/"))
                else:
                    with open(os.path.join("tmp", project.name + ".txt"), "w") as f:
                        f.write(project.description)
        for item in futures:
            e = item.exception()
            if e:
                raise e

    def get_gitlab_projects(self):
        page = 0
        all_projects = {}
        while True:
            projects = self.gl.projects.owned(per_page=10, page=page)
            page += 1
            if not projects:
                break
            for item in projects:
                if item.visibility_level == gitlab.VISIBILITY_PUBLIC:  # or "githubmirror" not in item.tag_list:
                    continue
                all_projects[item.name] = item
        return all_projects


def main():
    with open("creds.json") as f:
        creds = json.load(f)

    gitlab_api = gitlab.Gitlab(creds["gitlab"]["url"], creds["gitlab"]["token"], api_version=3)

    with SSHAgent() as agent:
        check_call(["ssh-add", creds["identity"]], env={"SSH_AUTH_SOCK": agent})
        DlGitlabProjects(agent, gitlab_api).run()


if __name__ == '__main__':
    main()
