# hitlist-downloader

This small python script will download the latest [IPv6 hitlist](https://ipv6hitlist.github.io/) containing IPv6 addresses that got a hit on UDP/53.
Have a look at the `.env` file for configuration. Provide a `URL` which contains `username:password` for authentication. The URL should contain the path `ipv6-hitlist-service/registered/`.

# How to use?

* Pull the latest image
  * `sudo docker pull ghcr.io/steffsas/hitlist-downloader:latest`
* Create an environment file `.env` that contains `URL=https://<username>:<password>@<base-url-ipv6hitlist>/ipv6-hitlist-service/registered/`
  * Hint: First ask the owner for access to their files, see https://ipv6hitlist.github.io/
* Run the Docker container
  * `sudo docker run -v $(pwd)/.env:/app/.env -v $(pwd)/output/:/app/output/ ghcr.io/steffsas/hitlist-downloader:latest`
  * Hint: You can also use `-e URL=<URL>` flag, but this will record the credentials in your shell history