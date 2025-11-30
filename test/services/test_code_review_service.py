import src.configs.config
from loguru import logger
import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from gidgethub.aiohttp import GitHubAPI
import aiohttp

from src.services.code_review_service import CodeReviewService
from src.services.gh_service import GithubService

# Load environment variables from .env file
load_dotenv()

@pytest.mark.integration
class TestCodeReviewServiceIntegration:
    """
    A test class for full, end-to-end integration tests of the CodeReviewService.
    These tests require a valid GITHUB_TOKEN and make real API calls.
    """
    
    @pytest_asyncio.fixture(scope="function", autouse=True)
    async def services(self):
        """
        Set up the necessary service instances for all tests in this class.
        This runs once before any tests in the module are executed.
        """
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.error("GITHUB_TOKEN not found in environment. Skipping integration tests.")
            pytest.skip("SKIPPING INTEGRATION TESTS: GITHUB_TOKEN not found in environment.")
            
        async with aiohttp.ClientSession() as session:
            gh_api = GitHubAPI(session, "py-webhook-svc-tester", oauth_token=github_token)
            self.gh_service = GithubService(gh=gh_api)
            self.code_review_service = CodeReviewService(gs=self.gh_service)
            yield
        # Teardown is handled by the async with block

    @pytest.mark.asyncio
    async def test_get_code_review_rpt_integration_success(self):
        """Tests the success case for get_code_review_rpt."""
        pr_url = "https://github.com/nvd11/py-webhook-svc/pull/5"
        report = await self.code_review_service.get_code_review_rpt(pr_url, "dummy_token")
        assert isinstance(report, dict) and 'review_report' in report and len(report['review_report']) > 0

    @pytest.mark.asyncio
    async def test_get_code_review_rpt_integration_invalid_url(self):
        """
        Tests the failure case for get_code_review_rpt where the URL is invalid.
        The review service returns a review_report with an error message.
        """
        pr_url = "https://github.com/this/repo-does-not-exist/pull/99999"
        report = await self.code_review_service.get_code_review_rpt(pr_url, "dummy_token")
        
        # Assert that the service correctly relays the "not found" message.
        assert isinstance(report, dict)
        assert 'review_report' in report
        
        # A list of possible error substrings to check for, making the test more robust.
        possible_error_messages = [
            "unable to find",
            "couldn't find",
            "not found",
            "error",
            "sorry",
        ]
        
        review_message = report['review_report'].lower()
        # Check if any of the possible messages are in the review message.
        assert any(msg in review_message for msg in possible_error_messages)

    @pytest.mark.asyncio
    async def test_code_review_full_workflow(self):
        """
        Tests the full end-to-end workflow of the code_review method.
        It gets a review and posts it as a comment to a real PR.
        """
        # Arrange: Use a real PR for testing. 
        # Make sure the GITHUB_TOKEN has write access to this repo.
        pr_url = "https://github.com/nvd11/py-webhook-svc/pull/5"
        logger.info(f"Starting full workflow test for PR: {pr_url}")
        # Act
        response = await self.code_review_service.code_review(pr_url, "dummy_token")
        
        # Assert
        # A successful comment posting returns a dictionary with details.
        assert isinstance(response, dict)
        assert "id" in response
        assert "body" in response
        assert response["body"].strip() != "" # Ensure the review body is not empty
        logger.info(f"Successfully posted comment with ID: {response['id']}")
