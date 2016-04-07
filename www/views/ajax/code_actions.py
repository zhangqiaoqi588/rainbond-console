# -*- coding: utf8 -*-
import datetime
import json

from django.views.decorators.cache import never_cache
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from www.views import AuthedView
from www.models import Users
from www.decorator import perm_required
from www.db import BaseConnection
from www.tenantservice.baseservice import CodeRepositoriesService

import logging
from django.template.defaultfilters import length
logger = logging.getLogger('default')

codeRepositoriesService = CodeRepositoriesService()

class CodeAction(AuthedView):    
    @perm_required('tenant_account')
    def get(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.GET.get("action", "")
            if action == "gitlab":
                tenant_id = self.tenant.tenant_id
                dsn = BaseConnection()
                query_sql = '''
                    select distinct git_url, git_project_id from tenant_service s where s.tenant_id = "{tenant_id}" and code_from="gitlab_new" and git_project_id>0 
                '''.format(tenant_id=tenant_id)
                sqlobjList = dsn.query(query_sql)            
                if sqlobjList is not None:
                    arr = []
                    for sqlobj in sqlobjList:
                        d = {}
                        d["code_repos"] = sqlobj.git_url
                        d["code_user"] = sqlobj.git_url.split(":")[1].split("/")[0]
                        d["code_project_name"] = sqlobj.git_url.split(":")[1].split("/")[1].split(".")[0]
                        d["code_id"] = sqlobj.git_project_id
                        arr.append(d)
                    data["data"] = arr
                    data["status"] = "success"
            elif action == "github":
                token = self.user.github_token
                if token is not None:
                    repos = codeRepositoriesService.getgGitHubAllRepos(token)
                    reposList = json.loads(repos)
                    if isinstance(reposList, dict):
                        data["status"] = "unauthorized"
                        data["url"] = codeRepositoriesService.gitHub_authorize_url(self.user)
                    else:                        
                        arr = []
                        for reposJson in reposList:
                            d = {}
                            clone_url = reposJson["clone_url"]
                            code_id = reposJson["id"]
                            d["code_id"] = code_id
                            d["code_repos"] = clone_url
                            d["code_user"] = clone_url.split("/")[3]
                            d["code_project_name"] = clone_url.split("/")[4].split(".")[0]
                            arr.append(d)
                        data["data"] = arr
                        data["status"] = "success"
                else:
                    data["status"] = "unauthorized"
                    data["url"] = codeRepositoriesService.gitHub_authorize_url(self.user)
        except Exception as e:
            logger.exception(e)
        return JsonResponse(data, status=200)
    
    @perm_required('tenant_account')
    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST["action"]
            if action == "gitlab":
                code_id = request.POST["code_id"]
                if code_id != "undefined":
                    branchList = codeRepositoriesService.getProjectBranches(code_id)
                    arr = []
                    if type(branchList) is str:
                        branchList = json.loads(branchList)
                    for branch in branchList:
                        d = {}
                        d["ref"] = branch["name"]
                        d["version"] = branch["name"]
                        arr.append(d)
                    data["data"] = arr
                    data["status"] = "success"
                    data["code_id"] = code_id
            elif action == "github":
                user = request.POST["user"]
                repos = request.POST["repos"]
                code_id = request.POST["code_id"]
                token = self.user.github_token
                data["code_id"] = code_id
                if token is not None:
                    repos = codeRepositoriesService.gitHub_ReposRefs(user, repos, token)
                    reposList = json.loads(repos)
                    if isinstance(reposList, dict):
                        data["status"] = "unauthorized"
                        data["url"] = codeRepositoriesService.gitHub_authorize_url(self.user)
                    else:
                        arr = []
                        reposList.sort(reverse=True)
                        for reposJson in reposList:
                            d = {}
                            ref = reposJson["ref"]
                            d["ref"] = ref
                            d["version"] = ref.split("/")[2]
                            arr.append(d)
                        data["data"] = arr
                        data["status"] = "success"
                else:
                    data["status"] = "unauthorized"
                    data["url"] = codeRepositoriesService.gitHub_authorize_url(self.user)
        except Exception as e:
            logger.exception(e)
        return JsonResponse(data, status=200)
    
