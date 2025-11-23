import os
import src.configs.config
from loguru import logger

import aiohttp
from gidgethub.aiohttp import GitHubAPI


class GithubService:
    def __init__(self, oauth_token: str):
        self.oauth_token = oauth_token
        self._session: aiohttp.ClientSession | None = None
        self.gh: GitHubAPI | None = None

    async def __aenter__(self):
        """
        在进入 'async with' 块时被调用。
        负责创建 session 和 GitHubAPI 客户端。
        """
        self._session = aiohttp.ClientSession()
        
        # The second argument to GitHubAPI is 'requester'.
        # This is used as the User-Agent header for all API requests.
        # GitHub requires a valid User-Agent, and it's best practice
        # to use your app's name or your GitHub username.
        self.gh = GitHubAPI(
            self._session, 
            "py-webhook-svc",
            oauth_token=self.oauth_token
        )
        
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        在退出 'async with' 块时被调用。
        负责安全地关闭 session。
        """
        if self._session and not self._session.closed:
            await self._session.close()

    
    
    
    async def get_user_info(self):
        return await self.gh.getitem("/user")

    
    
    async def get_repo_info(self, repo_name: str):
        return await self.gh.getitem(f"/repos/{repo_name}")

    async def get_repo_issues(self, repo_name: str):
        return await self.gh.getiter(f"/repos/{repo_name}/issues")


  

    async def post_general_pr_comment(self, owner: str, repo_name: str, pr_number: int, comment_body: str):
        """
        在 PR 的主时间线上发表一个通用评论。
         why we use the issue comments url to make a comment to a pr?
        # bYou've raised a very classic and core question in the history of GitHub API design!

        #Short answer: Yes, in GitHub's data model, a Pull Request is simply an Issue, with some additional attributes 
        # (such as commits and diffs). So this isn't imprecise; it's a deliberate, inheritance-based design.

        #Long answer: When GitHub first started, they had a very simple design: every piece of content (Issues, Pull Requests, etc.) 
        # was just an Issue in the database. So you could use the same endpoints for both.

        #Over time, they added more features to Pull Requests (like commits and diffs), but they kept the same endpoint for comments.
        # This is why you can use the same endpoint for both.
        """
        # 注意: 使用 issues API endpoint
        url = f"/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        return await self.gh.post(url, data={"body": comment_body})
        

    async def post_line_comment_in_pr(self, owner: str, repo_name: str, pr_number: int, comment_body: str, commit_id: str, file_path: str, line_number: int):
        """
        在 PR 的某一行代码上发表一个审查评论 (Review Comment)。
        """
        # 注意: 使用 pulls API endpoint
        url = f"/repos/{owner}/{repo_name}/pulls/{pr_number}/comments"
        payload = {
            "body": comment_body,
            "commit_id": commit_id,
            "path": file_path,
            "line": line_number,
            "side": "LEFT",
            "start_line": line_number,
            "start_side": "LEFT",
        }
        await self.gh.post(url, data=payload)
        print(f"Posted line comment to {file_path}:{line_number} in PR #{pr_number}")


