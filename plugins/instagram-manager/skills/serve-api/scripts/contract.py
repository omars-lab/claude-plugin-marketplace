"""contract.py — the shape of everything the data API answers with, and of what it accepts.

The read models are the shape send-topics writes to out/travel/<area>.yaml and out/<topic>.yaml, so
a repo that reads those files and a hub that calls the API read the same thing. Every model forbids
fields it does not name: test_api.py runs send-topics on invented data and validates each file
against these, so a field added there and not here fails the test instead of slipping past
consumers. The JSON Schema files in ../schema/ are written from these models (`api.py --schema`).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- what a consumer reads --------------------------------------------------------------------------

class Spot(Strict):
    """One place a save names: a beach, a café, a trailhead."""
    name: str = Field(description="The spot's name.")
    said: Optional[str] = Field(None, description="The caption's (or the video's) own words for it.")
    near: Optional[str] = Field(None, description="The town, park or area it sits in.")
    kind: Optional[str] = Field(None, description="OpenStreetMap's kind: restaurant, beach, viewpoint…")
    lat: Optional[float] = Field(None, description="Latitude, from OpenStreetMap. Only when `exact`.")
    lon: Optional[float] = Field(None, description="Longitude, from OpenStreetMap. Only when `exact`.")
    osm: Optional[str] = Field(None, description="OpenStreetMap id, such as node/123.")
    wikidata: Optional[str] = Field(None, description="Wikidata id, when OpenStreetMap has one.")
    map: str = Field(description="A Google Maps link: the exact place when its place id is kept, else a "
                                 "search for the name in its town.")
    google_id: Optional[str] = Field(None, description="Google's place id, when one is kept. Nothing else "
                                                       "of Google's is kept.")
    from_: Literal["caption", "video"] = Field(alias="from", description="Where the name was read.")
    exact: bool = Field(description="True when pinned at the spot itself; false when OpenStreetMap does "
                                    "not list it and it stands at its town (no lat/lon then).")
    still: Optional[str] = Field(None, description="A still from the video, a path in the media folder.")
    clip: Optional[str] = Field(None, description="A 3 second clip, a path in the media folder.")
    t: Optional[float] = Field(None, description="Seconds into the video where the still is.")
    still_from: Optional[Literal["name", "area"]] = Field(
        None, description="name: the spot's name is on screen; area: a shot of its area.")
    area: Optional[str] = Field(None, description="The area the still shows, when still_from is area.")


class Save(Strict):
    """One saved post, as one file lists it."""
    code: str = Field(description="Instagram's post code.")
    url: str
    creator: Optional[str] = Field(None, description="The account that posted it.")
    saved_at: Optional[str] = Field(None, description="When it was saved, from the export.")
    kind: Optional[str] = Field(None, description="post or reel.")
    topics: List[str]
    purposes: Optional[List[str]] = Field(None, description="eat, stay, do… for travel saves.")
    places: Optional[List[str]] = Field(None, description="The most exact places it is tagged with.")
    thumb: Optional[str] = Field(None, description="Its thumbnail, a path in the media folder.")
    also_in: Optional[List[str]] = Field(None, description="The other files it is in: topics, and "
                                                           "travel/<area> for other areas.")
    items: List[Spot] = Field(description="Its spots in this file's area (travel); empty for other topics.")


class TopicFile(Strict):
    """One file's content: a travel area (out/travel/<area>.yaml) or a topic (out/<topic>.yaml)."""
    topic: str
    area: Optional[str] = Field(None, description="The state or country, for a travel file.")
    feeds: List[str] = Field(description="The repos this topic feeds.")
    scope: str = Field(description="Which saves are in: every tagged save, or a pilot's.")
    count: int
    saves: List[Save]


class SaveAll(Strict):
    """One saved post with everything about it across files: every area's spots together."""
    code: str
    url: str
    creator: Optional[str] = None
    saved_at: Optional[str] = None
    kind: Optional[str] = None
    topics: List[str]
    purposes: Optional[List[str]] = None
    places: Optional[List[str]] = None
    thumb: Optional[str] = None
    files: List[str] = Field(description="Every file it is in: travel/<area> and topics.")
    items: List[Spot]


class SpotAt(Spot):
    """A spot in the flat list of every location, with the save that names it."""
    code: str = Field(description="The save that names it.")
    area_file: str = Field(description="Its travel file, travel/<area>.")


class FileSummary(Strict):
    file: str = Field(description="travel/<area> or a topic name.")
    topic: str
    area: Optional[str] = None
    feeds: List[str]
    saves: int
    spots: int


class Page(Strict):
    total: int = Field(description="How many match, before limit and offset.")
    offset: int
    limit: int


class SavesPage(Page):
    saves: List[SaveAll]


class SpotsPage(Page):
    spots: List[SpotAt]


class Health(Strict):
    ok: bool
    loaded_at: Optional[str] = Field(None, description="When the data was last read (UTC).")
    load_ms: Optional[int] = None
    reloads: int
    saves: int
    spots: int
    scope: Optional[str] = None
    error: Optional[str] = Field(None, description="Why the last reload failed; the data before it is "
                                                   "still served.")


# --- what the hub manages ---------------------------------------------------------------------------

class TagsIn(Strict):
    """A person's tags for one save. The entry is marked `by: hand`, so no tagging round changes it."""
    topics: List[str]
    places: List[str] = Field(description="Places from the place list (config and data/places.yaml).")
    purposes: Optional[List[str]] = None


class ReviewIn(Strict):
    """A decision on a spot OpenStreetMap did not find (data/pins-review.yaml). `make locate-merge`
    then applies it: ok keeps the find, drop leaves the spot out, lookup searches another name."""
    action: Literal["ok", "drop", "lookup"]
    name: Optional[str] = Field(None, description="The name to search, for lookup.")


class GoogleIn(Strict):
    """A decision on a spot's Google place. none: no candidate is this spot. chain: any branch will
    do. Picking one place needs Google's id check and so the key, which never enters the API; the
    answer then gives the `make google-ids PICK=…` line to run instead."""
    verdict: Literal["none", "chain", "pick"]
    place_id: Optional[str] = None


class Problem(BaseModel):
    model_config = ConfigDict(extra="allow")
    ev: str


class Written(Strict):
    ok: bool
    file: str
    message: str
    run: Optional[str] = Field(None, description="A make line still to run, when the change needs one.")


class GoogleWaiting(Strict):
    key: str
    query: str
    codes: List[str]
    ids: List[str] = Field(description="Google's candidate place ids, in Google's order.")


class ReviewWaiting(Strict):
    code: str
    index: int = Field(description="Its place in the save's list, for POST /v1/manage/review/{code}/{index}.")
    said: Optional[str] = None
    name: Optional[str] = None
    near: Optional[str] = None
    why: Optional[str] = None


class Move(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str


class Link(Strict):
    label: str
    url: str
    note: str


class Decisions(Strict):
    """Everything waiting on a person, as the decisions page lists it."""
    google: List[GoogleWaiting]
    review: List[ReviewWaiting]
    town_only: int = Field(description="Spots shown at their town with a name search; nothing to decide.")
    moves: List[Move] = Field(description="Saves to move to another collection, by hand in the app.")
    answers_to_merge: dict = Field(description="kind → agent answer files waiting for their make target.")
    videos_waiting: int
    elsewhere: List[Link]


SCHEMAS = {"spot": Spot, "save": Save, "topic-file": TopicFile, "save-all": SaveAll, "spot-at": SpotAt,
           "file-summary": FileSummary, "tags-in": TagsIn, "review-in": ReviewIn, "google-in": GoogleIn,
           "decisions": Decisions, "health": Health}
