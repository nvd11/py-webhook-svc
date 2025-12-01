import src.configs.config
from loguru import logger

import aiohttp
import asyncio
from gidgethub.aiohttp import GitHubAPI
import os
from gidgethub import sansio
import pytest


def test_hello():
    logger.info("test hello!")


@pytest.mark.asyncio
async def test_github_api_creation():
    """
    Tests that the GithubAPI object can be created without errors.
    """
    logger.info("Testing GitHubAPI creation...")
    logger.info(f"GITHUB_TOKEN: {os.getenv('GITHUB_TOKEN')[:10]}...")
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "nvd11", oauth_token=os.getenv("GITHUB_TOKEN"))
        assert gh is not None


        # You can add more specific assertions here.
        # For example, check if the headers are set correctly.
        headers = sansio.create_headers("nvd11", oauth_token=os.getenv("GITHUB_TOKEN"))
        assert "authorization" in headers
        assert headers["authorization"] == f"token {os.getenv('GITHUB_TOKEN')}"




