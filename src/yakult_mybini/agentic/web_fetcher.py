import re
import requests
from typing import Dict
from bs4 import BeautifulSoup


class WebFetcher:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    ]

    def fetch(self, url: str, max_chars: int = 8000, timeout: int = 15) -> Dict:
        try:
            headers = {
                "User-Agent": self.USER_AGENTS[hash(url) % len(self.USER_AGENTS)],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5,id;q=0.3",
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if (
                "text/html" not in content_type
                and "application/xhtml" not in content_type
            ):
                return {
                    "success": True,
                    "url": url,
                    "title": "",
                    "description": "",
                    "content": f"[Non-HTML content: {content_type}]",
                    "links": [],
                }

            soup = BeautifulSoup(resp.text, "lxml")

            for tag in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "footer",
                    "header",
                    "aside",
                    "noscript",
                    "iframe",
                    "form",
                    "svg",
                ]
            ):
                tag.decompose()

            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            description = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc and meta_desc.get("content"):
                description = meta_desc["content"].strip()

            for tag in soup(
                [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                    "p",
                    "li",
                    "pre",
                    "code",
                    "blockquote",
                    "th",
                    "td",
                    "dt",
                    "dd",
                ]
            ):
                tag_text = tag.get_text(strip=True)
                if tag_text:
                    tag_name = tag.name
                    if tag_name.startswith("h"):
                        prefix = "#" * int(tag_name[1])
                        tag.insert_after(f"\n{prefix} ")
                    elif tag_name in ("li", "dt", "dd"):
                        tag.insert_after("\n- ")
                    elif tag_name in ("th", "td"):
                        tag.insert_after(" | ")
                    elif tag_name == "pre":
                        tag.insert_after("\n```\n")
                        tag.insert_before("\n```\n")
                    elif tag_name == "blockquote":
                        tag.insert_after("\n> ")
                    else:
                        tag.insert_after("\n")

            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\n\s*\n", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            text = text.strip()

            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[...truncated]"

            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True)
                if href.startswith("http") and link_text:
                    links.append({"text": link_text[:80], "url": href})

            return {
                "success": True,
                "url": url,
                "title": title,
                "description": description[:300],
                "content": text,
                "links": links[:30],
            }

        except requests.Timeout:
            return {
                "success": False,
                "url": url,
                "error": f"Request timed out after {timeout}s",
            }
        except requests.HTTPError as e:
            return {
                "success": False,
                "url": url,
                "error": f"HTTP {e.response.status_code}",
            }
        except requests.ConnectionError:
            return {
                "success": False,
                "url": url,
                "error": "Connection failed (DNS or unreachable)",
            }
        except Exception as e:
            return {"success": False, "url": url, "error": str(e)}
