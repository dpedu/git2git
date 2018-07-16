#!/usr/bin/env python3
import json
import gitea
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


class GiteaToGithubMirror(object):
    def __init__(self, creds, agent):
        self.creds = creds
        self.agent = agent

        self.ge = gitea.Gitea(self.creds["gitea"]["url"], self.creds["gitea"]["token"])
        self.gh = github.Github(self.creds["github"]["username"], self.creds["github"]["password"])
        self.ghu = self.gh.get_user()

        if not os.path.exists("./tmp"):
            os.mkdir("./tmp")

    def run(self):
        self.github_projects = self.get_github_projects()
        self.gitea_projects = self.get_gitea_projects()

        print("{} projects to check".format(len(self.gitea_projects)))
        visited = []
        for project_name, project in self.gitea_projects.items():
            if project_name in visited:
                continue
            visited.append(project_name)
            print("({}/{}) Mirroring {}".format(len(visited), len(self.gitea_projects), project_name))
            self.mirror_to_gh(project_name)

    def get_gitea_projects(self):
        projects = {}
        for project in filter(lambda x: x["private"] == False and x["empty"] == False, self.ge.get_user_repos()):
            projects[project['name']] = project
        return projects

    def get_github_projects(self):
        all_projects = {}
        for repo in self.ghu.get_repos():
            all_projects[repo.name] = repo
        return all_projects

    def mirror_to_gh(self, project_name):
        assert project_name
        source = self.gitea_projects[project_name]
        dest = None

        if project_name in self.github_projects:
            dest = self.github_projects[project_name]
        else:
            print("{} not found in github, creating".format(project_name))
            dest = self.ghu.create_repo(name=source['name'],
                                        description=source['description'],
                                        homepage=source['html_url'])  # Gitea project url

        repo_dir = os.path.join("tmp", source['name'])

        if not os.path.exists(repo_dir):
            try:
                check_call(["git", "clone", source['ssh_url'], source['name']], cwd="./tmp/")
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
        GiteaToGithubMirror(creds, agent).run()


if __name__ == '__main__':
    main()
