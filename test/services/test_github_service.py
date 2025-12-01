import src.configs.config
from loguru import logger

import pytest
from src.services.gh_service import GithubService
import os

import aiohttp
from gidgethub.aiohttp import GitHubAPI

@pytest.mark.asyncio
async def test_get_user_info():
    """
    Tests the GithubService to ensure it can be created and used
    
    Note: This is an integration test and requires a valid GITHUB_TOKEN.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN is not set, skipping integration test.")

    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "py-webhook-svc", oauth_token=token, base_url="https://api.github.com")
        gh_service = GithubService(gh)
        assert gh_service.gh is not None
        user_info = await gh_service.get_user_info()
        logger.info(user_info)

@pytest.mark.asyncio
async def test_make_comment_to_pr():
    """
    Tests the GithubService to ensure it can make a comment to a pr
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN is not set, skipping integration test.")

    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "py-webhook-svc", oauth_token=token, base_url="https://api.github.com")
        gh_service = GithubService(gh)
        assert gh_service.gh is not None
        comment = await gh_service.post_general_pr_comment(owner="nvd11", repo_name="Terraform-GCP-config", pr_number=1, comment_body="This is a test comment")
        logger.info(comment)
