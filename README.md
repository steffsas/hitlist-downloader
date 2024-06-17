# hitlist-downloader

This small python script will download the latest [IPv6 hitlist](https://ipv6hitlist.github.io/) containing IPv6 addresses that got a hit on UDP/53.
Have a look at the `.env` file for configuration. Provide a `URL` which contains `username:password` for authentication. The URL should contain the path `ipv6-hitlist-service/registered/`.