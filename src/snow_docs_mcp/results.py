"""What the tools return: one model per result, as the client sees it (and as the panel and
the command line read it). Field descriptions are part of each tool's schema."""

from __future__ import annotations

from pydantic import BaseModel, Field

from snow_docs_mcp import config


class Hit(BaseModel):
    id: str = Field(description="Pass to snow_docs_read; cite it as [id].")
    release: str
    page_title: str
    url: str = Field(
        "", description="The page on docs.servicenow.com when the docs name it, else its source."
    )
    heading_path: str
    product: str
    snippet: str
    score: float = Field(description="Reranker relevance; higher is better.")


class SearchResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    hits: list[Hit] = []


class ReadResult(BaseModel):
    ok: bool
    message: str
    id: str = ""
    title: str = ""
    url: str = ""
    heading_path: str = ""
    content: str = ""
    truncated: bool = False


class ReleaseStatus(BaseModel):
    release: str
    state: str
    message: str
    progress: float
    snapshot: str = Field("", description="Docs snapshot in use (date of the docs commit).")
    chunks: int | None = None


class StatusResult(BaseModel):
    ok: bool = Field(description="True when the default release can be searched.")
    default_release: str
    releases: list[ReleaseStatus]
    models: str
    update_note: str = ""
    data_folder: str
    server_version: str = config.VERSION


class SectionDiff(BaseModel):
    heading_path: str
    change: str = Field(description="added, removed or changed (australia -> brazil).")
    changed_words: int
    australia_id: str = Field("", description="Pass to snow_docs_read; empty when added.")
    brazil_id: str = Field("", description="Pass to snow_docs_read; empty when removed.")
    australia_excerpt: str = ""
    brazil_excerpt: str = ""
    small: bool = Field(
        False, description="A rewording of a few words; the excerpts show the words around it."
    )


class ChangedPage(BaseModel):
    page: str = Field(description="The page's path; pass it as `page` to compare it alone.")
    page_title: str
    product: str
    australia_url: str = ""
    brazil_url: str = ""
    sections: list[SectionDiff] = []
    minor_changes: int = Field(0, description="How many of the sections are marked small.")
    sections_left_out: int = Field(0, description="Dropped to keep the result short.")


class NotesPage(BaseModel):
    id: str = Field(description="Pass to snow_docs_read for the whole release-notes page.")
    application: str


class CompareResult(BaseModel):
    ok: bool
    message: str
    australia_snapshot: str = ""
    brazil_snapshot: str = ""
    release_notes: list[Hit] = Field(
        [], description="ServiceNow's own release notes for upgrades from Australia to Brazil."
    )
    more_release_notes: list[NotesPage] = Field(
        [],
        description="Other release-notes pages whose application name shares a word with the query.",
    )
    changed_pages: list[ChangedPage] = []
    only_in_australia: list[str] = []
    only_in_brazil: list[str] = []


class ApiParam(BaseModel):
    name: str
    type: str
    description: str


class ApiClass(BaseModel):
    class_name: str = Field(description='As the docs write it, e.g. "Scoped GlideRecord".')
    members: list[str] = Field(description="Signatures of its methods; properties by name.")
    page_ids: list[str] = Field(description="The class's page(s); pass to snow_docs_read.")


class ApiMethod(BaseModel):
    class_name: str
    name: str
    kind: str
    signature: str
    parameters: list[ApiParam] = []
    returns: str = ""
    returns_description: str = ""
    description: str = ""
    example: str = ""
    id: str = Field(description="Pass to snow_docs_read for the full section; cite it as [id].")
    url: str = ""


class ApiEndpoint(BaseModel):
    api: str
    verb: str
    path: str
    default_url: str = ""
    description: str = ""
    path_parameters: list[ApiParam] = []
    query_parameters: list[ApiParam] = []
    body_parameters: list[ApiParam] = []
    id: str = Field(description="Pass to snow_docs_read for the full section; cite it as [id].")
    url: str = ""


class ApiResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    kind: str = Field("", description="class, method, rest_api, endpoint or not_found")
    classes: list[ApiClass] = []
    methods: list[ApiMethod] = []
    endpoints: list[ApiEndpoint] = []
    suggestions: list[str] = []


class BrowseFolder(BaseModel):
    name: str
    path: str = Field(description="Pass as `folder` to open it.")
    pages: int = Field(description="Pages in it, at any depth.")


class BrowsePage(BaseModel):
    title: str
    id: str = Field(description="Pass to snow_docs_read for the whole page; cite it as [id].")


class BrowseResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    path: str = Field(
        "", description="Where this listing is, e.g. it-service-management/incident-management."
    )
    folders: list[BrowseFolder] = []
    pages: list[BrowsePage] = []
    pages_left_out: int = 0


class SdkInstance(BaseModel):
    alias: str
    host: str
    auth_type: str = Field(description="basic or oauth")
    default: bool


class SdkStatusResult(BaseModel):
    ok: bool
    message: str
    installed: bool = False
    version: str = ""
    instances: list[SdkInstance] = []


class SdkTopic(BaseModel):
    name: str
    keywords: str = ""


class SdkExplainResult(BaseModel):
    ok: bool
    message: str
    version: str = ""
    topic: str = ""
    content: str = ""
    truncated: bool = False
    topics: list[SdkTopic] = []


class OpenResult(BaseModel):
    ok: bool
    message: str
    id: str = Field("", description="The page's id.")
    focus: str = Field("", description="The section to start at; empty for the top of the page.")
    title: str = ""
    url: str = ""
    release: str = ""
    product: str = ""
    headings: list[str] = []


class ScriptFinding(BaseModel):
    kind: str = Field(description="method or table")
    name: str = Field(description='"GlideRecord.addEncodedQuerry", or a table name')
    line: int
    suggestions: list[str] = []


class ScriptCheckResult(BaseModel):
    ok: bool
    message: str
    release: str = ""
    snapshot: str = ""
    checked_calls: int = Field(0, description="Calls on objects whose class could be told.")
    checked_tables: int = 0
    findings: list[ScriptFinding] = []
