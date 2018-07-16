from mirror import SSHAgent
from subprocess import check_call
from collections import defaultdict
import json
import gitlab


class DlGitlabProjects(object):
    def __init__(self, agent, gl):
        self.agent = agent
        self.gl = gl

    def run(self):
        projects = self.get_gitlab_projects()
        hooks = defaultdict(list)
        for name, project in projects.items():
            # import ipdb ; ipdb.set_trace()
            for hook in self.gl.project_hooks.list(project_id=project.id):
                hooks[name].append(hook.url)

            with open("./hooks.json", "w") as f:
                json.dump(dict(hooks), f, sort_keys=True, indent=4)

    def get_gitlab_projects(self):
        page = 0
        all_projects = {}
        while True:
            projects = self.gl.projects.list(per_page=10, page=page, owned=True)
            page += 1
            if not projects:
                break
            for item in projects:
                # if item.visibility == 'public':  # or "githubmirror" not in item.tag_list:
                #     continue
                all_projects[item.name] = item
        return all_projects


def main():
    with open("creds.json") as f:
        creds = json.load(f)

    gitlab_api = gitlab.Gitlab(creds["gitlab"]["url"], creds["gitlab"]["token"], api_version=4)

    with SSHAgent() as agent:
        check_call(["ssh-add", creds["identity"]], env={"SSH_AUTH_SOCK": agent})
        DlGitlabProjects(agent, gitlab_api).run()


if __name__ == '__main__':
    main()
