import os
import src.configs.config
from loguru import logger

import aiohttp
from gidgethub.aiohttp import GitHubAPI
import time
import jwt
from urllib.parse import urlparse

async def create_installation_access_token(
    app_id: str,
    private_key: str,
    installation_id: str,
    base_url: str = "https://api.github.com"
) -> str:
    """
    Manually create an installation access token.
    This is useful for GitHub Enterprise Server where gidgethub helpers might not work.
    """
    def generate_jwt(app_id, private_key):
        payload = {
            'iat': int(time.time()),
            'exp': int(time.time()) + (10 * 60),  # 10 minutes expiration
            'iss': app_id
        }
        return jwt.encode(payload, private_key, algorithm='RS256')

    jwt_token = generate_jwt(app_id, private_key)
    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }
    url = f"{base_url}/app/installations/{installation_id}/access_tokens"

    # Use a shared session if available, or create a new one
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers) as response:
            if response.status == 201:
                data = await response.json()
                return data.get('token')
            else:
                error_text = await response.text()
                logger.error(f"Failed to get installation token: {response.status} - {error_text}")
                return None


class GithubService:
    def __init__(self, gh: GitHubAPI):
        self.gh = gh

    async def get_user_info(self):
        return await self.gh.getitem("/user")

    
    
    async def get_repo_info(self, repo_name: str):
        return await self.gh.getitem(f"/repos/{repo_name}")

    async def get_repo_issues(self, repo_name: str):
        return await self.gh.getiter(f"/repos/{repo_name}/issues")

    async def post_comment_by_url(self, pr_url: str, comment_body: str):
        """
        Posts a general comment to a pull request by parsing its URL.
        """
        try:
            parsed_url = urlparse(pr_url)
            path_parts = parsed_url.path.strip('/').split('/')
            
            if len(path_parts) >= 4 and path_parts[2] == 'pull':
                owner, repo_name, _, pr_number_str = path_parts[:4]
                pr_number = int(pr_number_str)
                logger.info(f"Parsed PR URL: owner='{owner}', repo='{repo_name}', number={pr_number}")
                
                return await self.post_general_pr_comment(
                    owner=owner,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    comment_body=comment_body
                )
            else:
                logger.error(f"Invalid GitHub PR URL format: {pr_url}")
                return {"error": "Invalid GitHub PR URL format."}
        except (ValueError, IndexError) as e:
            logger.error(f"Could not parse PR URL '{pr_url}': {e}")
            return {"error": f"Could not parse URL: {e}"}

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
