from typing import Iterable, Optional

from snapstore.client import SnapstoreClient


class SnapstoreInfo:
    """
    Retrieve snap info through the snap Store API

    Ref:
    - https://api.snapcraft.io/docs/refresh.html
    - https://api.snapcraft.io/docs/info.html
    """

    def __init__(self, client: SnapstoreClient):
        self.client = client

    def raw_info_snap(
        self,
        snap: str,
        architecture: str | None = None,
        store: str | None = None,
        fields: Iterable[str] | None = None
    ) -> dict:
        """
        Return info for a specific snap, as retrieved from the
        `v2/snaps/info/{snap}` endpoint of the snap Store API.

        The result contains a `channel-map` with information about
        the different channels on which the snap is published.

        Ref: https://api.snapcraft.io/docs/info.html
        """
        params = {}
        if architecture:
            params["architecture"] = architecture
        if fields:
            params["fields"] = ",".join(field.strip() for field in fields)
        return self.client.get(
            endpoint=f"v2/snaps/info/{snap}",
            params=params,
            store=store,
        )

    def raw_refresh_one(
        self,
        snap: str,
        channel: str,
        architecture: str,
        store: str | None = None,
        fields: Iterable[str] | None = None,
    ) -> dict:
        """
        Return info for a specific snap, as retrieved from the
        `v2/snaps/refresh` endpoint of the snap Store API.

        Ref: https://api.snapcraft.io/docs/refresh.html
        """
        payload = {
            "context": [],
            "actions": [
                {
                    "name": snap,
                    "channel": channel,
                    "action": "download",
                    "instance-key": "",
                }
            ]
        }
        if fields:
            payload["fields"] = sorted(fields)
        response = self.client.post(
            endpoint="v2/snaps/refresh",
            payload=payload,
            store=store,
            headers={"Snap-Device-Architecture": architecture},
        )
        results = response["results"]
        if len(results) != 1:
            raise ValueError(
                f"Multiple results for {snap}={channel} on {architecture}"
            )
        result = results[0]
        if "error" in result:
            raise ValueError(result["error"]["message"])
        return result

    def info(
        self,
        snap: str,
        channel: str,
        architecture: str | None = None, *,
        store: str | None = None,
        fields: Iterable[str] | None = None
    ):
        """
        Return info for a specific snap. Use the `v2/snaps/info/{snap}`
        endpoint of the snap Store API and return the entry from the
        channel map that matches a specific channel and architecture.
        """
        try:
            track, risk = channel.split("/")
        except ValueError as error:
            raise ValueError(
                f"{channel} is not formatted as track/risk"
            ) from error
        response = self.raw_info_snap(snap, architecture, store, fields)
        for entry in response["channel-map"]:
            channel_dict = entry["channel"]
            if channel_dict["track"] == track and channel_dict["risk"] == risk:
                return entry
        raise ValueError(
            f"No info for {snap}={channel} on {architecture}"
        )

    def info_from_refresh(
        self,
        snap: str,
        channel: str,
        architecture: str, *,
        store: str | None = None,
        fields: Iterable[str] | None = None
    ):
        """
        Return info for a specific snap. Use the `v2/snaps/refresh`
        endpoint of the snap Store API and return the "snap" field of the
        result, along with the "effective channel".
        """
        response = self.raw_refresh_one(
            snap, channel, architecture, store, fields
        )
        return {
            **response["snap"],
            **{"effective-channel": response["effective-channel"]}
        }
