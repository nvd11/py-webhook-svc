from src.services.gh_service import GithubService
import src.configs.config
from loguru import logger
import aiohttp
import json

review_url="https://gateway.jpgcp.cloud/py-github-agent/review"



class CodeReviewService:
    def __init__(self, gs: GithubService):
        self.gs = gs

    async def get_code_review_rpt(self,prurl: str) -> dict:
        """
        Generate a code review report for the given pull request URL.
        Makes an HTTP POST request to an external service.
        Includes error handling for network issues and non-successful HTTP status codes.
        """
        payload = {"pull_request_url": prurl}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(review_url, json=payload, timeout=300) as resp:
                    # Check for successful HTTP status code
                    if resp.status == 200:
                        # Parse JSON response
                        response_data = await resp.json()
                        return response_data
                    else:
                        # Log error and return an informative message
                        error_text = await resp.text()
                        logger.error(
                            f"Failed to get code review report. "
                            f"Status: {resp.status}, Response: {error_text}"
                        )
                        return {"error": f"Received status {resp.status} from review service."}

        except aiohttp.ClientError as e:
            # Handle client-side exceptions (e.g., connection error, timeout)
            logger.error(f"AIOHTTP client error during code review request: {e}")
            return {"error": f"Could not connect to the review service. {e}"}
        except Exception as e:
            # Handle other unexpected exceptions
            logger.error(f"An unexpected error occurred: {e}")
            return {"error": f"An unexpected error occurred. {e}"}


    async def code_review(self, pr_url: str) -> str:
        """
        Wrapper function to get code review report.
        """
        words = "failed to get review.., please try again later."
        review_rs = await self.get_code_review_rpt(pr_url)
        if isinstance(review_rs, dict) and 'review_report' in review_rs:
            words = review_rs['review_report']
        elif isinstance(review_rs, dict):
            logger.error(f"Code review service returned an error: {review_rs}")
            words = json.dumps(review_rs)
        else:
            logger.error(f"Code review service returned an error: {review_rs}")
            words = str(review_rs)
        rs = await self.gs.post_comment_by_url(pr_url, words)
        return rs
