#!/usr/bin/env python3
import json
import gitlab
import github
import os
from shutil import rmtree
import re
from subprocess import check_call, check_output
from time import time
import signal


class SSHAgent(object):
    sockre = re.compile(r'SSH_AUTH_SOCK=(.*?);')
    pidre = re.compile(r'SSH_AGENT_PID=(\d*);', )

    def __init__(self, cluster=None):
        self.addargs = []
        if cluster:
            self.addargs.extend(['-a', os.path.join(cluster, 'agent.sock.{}'.format(int(time())))])

    def __enter__(self):
        output = check_output(['ssh-agent'] + self.addargs).decode("UTF-8")
        self.sock = self.sockre.search(output).group(1)
        self.pid = int(self.pidre.search(output).group(1))
        return self.sock

    def __exit__(self, errtype, value, traceback):
        os.kill(self.pid, signal.SIGHUP)


class GitlabToGithubMirror(object):
    def __init__(self, creds, agent):
        self.creds = creds
        self.agent = agent

        self.gl = gitlab.Gitlab(self.creds["gitlab"]["url"], self.creds["gitlab"]["token"], api_version=3)
        self.gh = github.Github(self.creds["github"]["username"], self.creds["github"]["password"])
        self.ghu = self.gh.get_user()

        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")

    def get_gitlab_projects(self):
        page = 0
        all_projects = {}
        while True:
            projects = self.gl.projects.owned(per_page=10, page=page)
            page += 1
            if not projects:
                break
            for item in projects:
                if item.visibility_level != gitlab.VISIBILITY_PUBLIC or "githubmirror" not in item.tag_list:
                    continue
                all_projects[item.name] = item
        return all_projects

    def get_github_projects(self):
        all_projects = {}
        for repo in self.ghu.get_repos():
            all_projects[repo.name] = repo
        return all_projects

    def run(self):
        self.github_projects = self.get_github_projects()
        self.gitlab_projects = self.get_gitlab_projects()

        print("{} projects to check".format(len(self.gitlab_projects)))
        visited = []
        for project_name, project in self.gitlab_projects.items():
            if project_name in visited:
                continue
            visited.append(project_name)
            print("({}/{}) Mirroring {}".format(len(visited), len(self.gitlab_projects), project_name))
            self.mirror_to_gh(project_name)

    def mirror_to_gh(self, project_name):
        assert project_name
        source = self.gitlab_projects[project_name]
        dest = None

        if project_name in self.github_projects:
            dest = self.github_projects[project_name]
        else:
            print("{} not found in github, creating".format(project_name))
            dest = self.ghu.create_repo(name=source.name,
                                        description=source.description,
                                        homepage=source.web_url)  # Gitlab url

        repo_dir = os.path.join("tmp", source.name)

        if not os.path.exists(repo_dir):
            try:
                check_call(["git", "clone", source.ssh_url_to_repo, source.name], cwd="./tmp/")
            except:
                rmtree(repo_dir)
                raise
            try:
                check_call(["git", "remote", "add", "github", dest.ssh_url], cwd=repo_dir)
            except:  # Remote already exists
                pass
        else:
            check_call(["git", "fetch"], cwd=repo_dir)
            check_call(["git", "pull", "origin", "master"], cwd=repo_dir)

        check_call(["git", "push", "-f", "-u", "github", "master"], cwd=repo_dir, env={"SSH_AUTH_SOCK": self.agent})
        print("Completed {}\n".format(project_name))


def main():
    with open("creds.json") as f:
        creds = json.load(f)

    with SSHAgent() as agent:
        check_call(["ssh-add", creds["identity"]], env={"SSH_AUTH_SOCK": agent})
        GitlabToGithubMirror(creds, agent).run()


if __name__ == '__main__':
    main()
