import hashlib
import io
import logging
from typing import Tuple, Optional
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class FetcherService:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def fetch_url(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Fetches URL content and extracts text.
        Returns (extracted_text, content_hash).
        If fetching fails, returns ("", None) to prevent LLM poisoning.
        """
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()

            raw_bytes = response.content
            content_hash = hashlib.sha256(raw_bytes).hexdigest()
            content_type = response.headers.get("content-type", "").lower()

            if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                text = self._extract_pdf_text(raw_bytes)
            else:
                text = self._extract_html_text(response.text)

            return text, content_hash

        except Exception as e:
            logger.warning(f"Could not fetch URL {url} ({e}). Skipping page body.")
            return "", None

    def _extract_html_text(self, html_content: str) -> str:
        soup = BeautifulSoup(html_content, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return "\n".join(chunk for chunk in chunks if chunk)

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        text = ""
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            text = ""
        return text
