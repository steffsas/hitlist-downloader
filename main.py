import httpx
import os
import lzma
import re
import pandas as pd
import logging
import sys

from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

URL_ENV = "URL"
LOG_FOLDER_ENV = "LOG_FOLDER"
DOWNLOAD_FOLDER_ENV = "DOWNLOAD_FOLDER"
OUTPUT_FOLDER_ENV = "OUTPUT_FOLDER"

logger = logging.getLogger(__name__)

def main() -> None:
    load_dotenv(".env", override=False)

    today = datetime.now().strftime("%Y-%m-%d")

    logFolder = os.getenv(LOG_FOLDER_ENV)
    if logFolder == None:
        logFolder = "logs"

    if not os.path.exists(logFolder):
        os.makedirs(logFolder)

    logging.basicConfig(
        filename=f"{logFolder}/{today}.log", level=logging.INFO,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    url = os.getenv(URL_ENV)
    if url == None:
        logger.error("URL not found in environment variables")
        return

    downloadFolder = os.getenv(DOWNLOAD_FOLDER_ENV)
    outputFolder = os.getenv(OUTPUT_FOLDER_ENV)

    if not os.path.exists(downloadFolder):
        os.makedirs(downloadFolder)

    if not os.path.exists(outputFolder):
        os.makedirs(outputFolder)

    soup = receiveSoup(url)
    outputLinks = getSortedLinks(soup)
    if len(outputLinks) == 0:
        logger.error("no links found")
        return
    
    # let's receive all outputs from the latest link
    outputLink = outputLinks[0][1]
    soup = receiveSoup(f"{url}/{outputLink}")
    if soup == None:
        return
    fileLinks = getSortedLinks(soup)
    if len(fileLinks) == 0:
        if len(outputLinks) == 1:
            logger.error("no links found")
            return
        
        # let's try the second latest link
        outputLink = outputLinks[1][1]
        soup = receiveSoup(f"{url}/{outputLink}")
        if soup == None:
            return
        fileLinks = getSortedLinks(soup)
        if len(fileLinks) == 0:
            logger.error("no links found")
            return
        
    # let's search for UDP links
    fileLink = ""
    for link, text in fileLinks:
        if "udp53" in text.lower():
            fileLink = link
            break
    else:
        logger.error("no udp53 link found")
        return

    # let's download the file
    downloadLink = f"{url}/{outputLink}{fileLink}"

    # let's get the date from the filename
    date = extractDateFromFilename(fileLink)
    if date == "":
        logger.info("date not found in filename, will use date ", today)
        date = today

    downloadedFile = f"{downloadFolder}/ipv6-udp-{date}.xz"

    if os.path.exists(downloadedFile):
        logger.warning("file already downloaded, exiting")
        return

    logger.info(f"download file: {fileLink}")
    r = httpx.get(downloadLink, follow_redirects=True)
    with open(downloadedFile, 'wb') as f:
        f.write(r.content)
    logger.info(f"file downloaded and written to {downloadedFile}")
    outputFile = f"{downloadFolder}/ipv6-udp-{date}.csv"
    
    # extract file with xz
    logger.info(f"extract {downloadedFile} file to {outputFile}")
    try:
        with lzma.open(downloadedFile, "rb") as f:
            fileContent = f.read()
        with open(outputFile, "wb") as f:
            f.write(fileContent)
        logger.info("file extracted")
    except Exception as e:
        logger.info("failed to extract file: ", e)

    # let's parse the downloaded csv
    ips = pd.read_csv(outputFile)
    outputTxt = f"{outputFolder}/ipv6-udp-{date}.txt"

    ips = pd.read_csv("downloads/ipv6-udp-2024-05-29.csv", delimiter=",")

    logger.info("got {0} ips, removing duplicates...".format(len(ips)))

    ips = ips[ips["success"] == 1][
        # for some reason saddr is the original destination
        ["saddr"]
    ].drop_duplicates(ignore_index=True, inplace=False)

    logger.info("will write {0} ips to {1}".format(len(ips), outputTxt))

    with open(outputTxt, "w") as f:
        for index, row in ips.iterrows():
            f.write(row["saddr"] + "\n")

    logger.info("done")

def receiveSoup(url: str) -> BeautifulSoup:
    response = httpx.get(url, follow_redirects=True)
    if response.status_code != 200:
        logger.error(f"failed to get page, status code {response.status_code}")
        return None
    return BeautifulSoup(response.text, "html.parser")

def getSortedLinks(soup: BeautifulSoup) -> list[tuple[str, str]]:
    # let's get all the links
    links = []
    for a in soup.find_all('a', href=True):
        if a.get_text() == "." or a.get_text() == ".." or a.get_text() == "../"  or a.get_text() == "./":
            continue
        links.append((a["href"], a.get_text()))
    
    # let's get the latest link
    sortedLinks = sorted(links, key=lambda x: x[1], reverse=True)
    return sortedLinks
    

def extractDateFromFilename(filename: str) -> str:
    # Define the regular expression pattern to match YYYY-MM-DD format
    pattern = r"(\d{4}-\d{2}-\d{2})"

    # Use re.search to find the match
    match = re.search(pattern, filename)

    if match:
        # Extract the date if there's a match
        date = match.group(1)
        return date
    else:
        logger.error("no date found in filename")
        return ""

if __name__ == "__main__":
    main()