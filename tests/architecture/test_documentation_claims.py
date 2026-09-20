r"""DOC-01 and DOC-02: the README's checkable claims, asserted as a gate.

`README.md` is the first file an evaluator opens and the only one that talks
about the whole project at once. That is exactly what makes it the document
most likely to be wrong: every sentence in it is about code that keeps moving,
and nothing in a test run has ever read it. A stale endpoint row, a `make`
target renamed six weeks ago, an ADR id off by one - none of those costs a
review comment today, and all of them cost the reader's trust in everything
else the file says.

So the README is held to the same standard as the rest of this repository:
observe the artifact, never restate it, and add a guard so an emptied
observation cannot pass (ADR-057, ADR-083, ADR-085, ADR-086, ADR-087, ADR-090,
and now ADR-102). Four documents are read here - `README.md`, `DECISION_LOG.md`,
`AI_WORKFLOW.md` and the `Makefile` - and every claim checked is one that can be
compared against something the code publishes.

**What this gate can see.** That the endpoint table and `app.openapi()` describe
the same set of operations, in both directions. That every `make <target>`
written in a code span or a fenced block is a real `.PHONY` target. That every
`ADR-NNN` cited in the README or in `AI_WORKFLOW.md` resolves to a heading in
the log. That the counts the README states for the ADRs and the import-linter
contracts are the counts in the files. That the rehearsal markers are a single
well-formed pair with commands inside them. And that `AI_WORKFLOW.md` still
carries its diagrams, covers every phase, and promises nothing for later.

**What it cannot see**, stated plainly because a gate that is trusted for more
than it does is worse than no gate: it reads documents and a published document.
It cannot tell whether a command *works*. `curl -s $API/health` could be
nonsense and every test here would stay green. That is the rehearsal script's
job (`scripts/clean-clone-rehearsal.sh`, plan 07-05): it clones the repository,
extracts the shell lines between the very markers checked below, and runs them.
The rehearsal also owns the checks that need the whole working tree - that every
path the README cites exists - because `docker-compose.yml`, `docker/`,
`.github/` and `.planning/` are deliberately absent from the test image.

**Deliberately NOT used: generating the README's endpoint table from the
application.** It would be less code and it would prove nothing. A generated
table agrees with `app.openapi()` by construction, so the one failure worth
catching - a human wrote a row that is not true - becomes impossible to express.
The table is written by hand precisely so that a test can disagree with it.

**Deliberately NOT used: scanning prose for `make <target>`.** The scan is
restricted to code spans and fenced blocks, because "make sure", "make an
account" and "make it green" are English. The cost is named: `make rehearse`
written in a sentence would escape. That is accepted - a command a reader is
meant to type belongs in code formatting, and the check that matters is over the
blocks the rehearsal actually executes.

**Deliberately NOT used: resolving the commit hashes in `AI_WORKFLOW.md`.**
Those were verified with `git cat-file -e` when they were written (plan 07-03),
and a test could re-verify them - on the host. The `test` stage installs `git`
but receives no `.git` directory, so the check would have to skip there, and a
totality check that skips in the container is the shape 06-REVIEW WR-06 recorded
as a hole. A check that runs in one of the two places it matters is not kept
here.

This gate adds no hook to `.pre-commit-config.yaml` and no step to
`.github/workflows/ci.yml`. CLAUDE.md's two-places rule applies to a gate that
needs its own invocation; this one rides inside `pytest`, which the hook set,
the Docker `test` stage and CI all already run. It does add one line to the
Dockerfile `test` stage, which is a different rule and a harder-won one: a test
that reads a repository-root file is green on the host and a collection error in
the container until that file is copied in (06-04, and now ADR-102).
"""

import re
from pathlib import Path
from typing import Any, Final

import pytest

from taskmanager.infrastructure.config.settings import Settings
from taskmanager.main import create_app
from tests.conftest import DATABASE_URL, JWT_SECRET

pytestmark = pytest.mark.unit

# tests/architecture/test_documentation_claims.py -> tests/architecture ->
# tests -> repository root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]

README: Final[Path] = ROOT / "README.md"
DECISION_LOG: Final[Path] = ROOT / "DECISION_LOG.md"
AI_WORKFLOW: Final[Path] = ROOT / "AI_WORKFLOW.md"
MAKEFILE: Final[Path] = ROOT / "Makefile"
IMPORTLINTER: Final[Path] = ROOT / ".importlinter"

# The four root documents this gate reads, and therefore the four the Dockerfile
# `test` stage has to copy. Named here so the failure message can say which one
# is missing rather than raising `FileNotFoundError` from whichever test ran
# first.
ROOT_DOCUMENTS: Final[tuple[Path, ...]] = (README, DECISION_LOG, AI_WORKFLOW, MAKEFILE)

# The brief's five genuine ambiguities and the entry that decides each, pinned
# as a table rather than derived. A generated map would agree with whatever the
# log happens to contain, which is the one thing it must not do: the claim being
# gated is that *these five questions* have answers, not that the log is
# internally consistent. DOC-03's own requirement wording is the source.
AMBIGUITY_ADRS: Final[dict[str, str]] = {
    "what the completion percentage is computed over": "ADR-009",
    "the status values and the moves allowed between them": "ADR-097",
    "the priority values, and what an absent priority means": "ADR-098",
    "who may be assigned to a task": "ADR-069",
    "what triggers the simulated invitation": "ADR-070",
}

ADR_CITATION: Final[re.Pattern[str]] = re.compile(r"\bADR-(\d{3})\b")
ADR_HEADING: Final[re.Pattern[str]] = re.compile(r"^## ADR-(\d{3}):", re.MULTILINE)

REHEARSAL_BEGIN: Final[str] = "<!-- rehearsal:begin -->"
REHEARSAL_END: Final[str] = "<!-- rehearsal:end -->"

# The heading the human/AI account lives under, and the seven phases it must
# cover. Located by heading rather than searched for document-wide: "Phase 3"
# appears in the incident log too, and a scan over the whole file would be
# satisfied by seven incidents and an empty section.
HUMAN_AI_HEADING: Final[str] = "## Human-Decided vs AI-Delegated"

PHASES: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7)

# Floors for the non-vacuity test. Each is the count observed when this gate was
# written, so a parser that silently stops matching fails rather than passing on
# an empty result. Floors and not equalities: the README gains rows as the API
# grows, and an equality here would be a test of the census.
MINIMUM_ENDPOINT_ROWS: Final[int] = 19
MINIMUM_ADR_CITATIONS: Final[int] = 5
MINIMUM_PHONY_TARGETS: Final[int] = 8
MINIMUM_MERMAID_BLOCKS: Final[int] = 3
MINIMUM_REHEARSAL_COMMANDS: Final[int] = 3

TABLE_ROW: Final[re.Pattern[str]] = re.compile(
    r"^\|[^|\n]+\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`([^`]+)`\s*\|",
    re.MULTILINE,
)

FENCED_BLOCK: Final[re.Pattern[str]] = re.compile(r"^```[a-z]*\n(.*?)^```", re.S | re.M)
INLINE_CODE: Final[re.Pattern[str]] = re.compile(r"`([^`\n]+)`")
MAKE_INVOCATION: Final[re.Pattern[str]] = re.compile(r"\bmake\s+([a-z][a-z0-9-]*)\b")


def _text(path: Path) -> str:
    """A document's contents, read once per call and never cached.

    Not a fixture: three of these are read by almost every test here, and a
    session-scoped cache would make a test that edits a file in `tmp_path`
    (there are none today) quietly read the stale copy.
    """
    return path.read_text(encoding="utf-8")


@pytest.fixture
def spec(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The published document, built from the real factory and no database.

    The same idiom `tests/architecture/test_openapi_completeness.py` uses, and
    for the same reason: `app.openapi()` is what a client reads, while
    `app.routes` holds one opaque object per included router on this stack.
    """
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)
    return create_app(Settings(_env_file=None)).openapi()


def _published_operations(spec: dict[str, Any]) -> set[tuple[str, str]]:
    """Every `(METHOD, path)` the application publishes."""
    return {
        (method.upper(), path)
        for path, item in spec["paths"].items()
        for method in item
    }


def _documented_operations() -> set[tuple[str, str]]:
    """Every `(METHOD, path)` the README's endpoint table names."""
    return {(method.upper(), path) for method, path in TABLE_ROW.findall(_text(README))}


def _code_fragments(text: str) -> list[str]:
    """Everything written as code in a Markdown document.

    Fenced blocks and inline spans, and nothing else. See the module docstring
    for why prose is out of scope.
    """
    return FENCED_BLOCK.findall(text) + INLINE_CODE.findall(text)


def _named_make_targets() -> set[str]:
    """Every `make <target>` the README writes in a code context."""
    return {
        target
        for fragment in _code_fragments(_text(README))
        for target in MAKE_INVOCATION.findall(fragment)
    }


def _phony_targets() -> set[str]:
    """Every target on the Makefile's `.PHONY` line.

    Read off the line rather than off the recipe headers: `.PHONY` is the
    declaration a reader of the Makefile sees, and a target present as a recipe
    but absent from `.PHONY` is its own (separate) defect.
    """
    for line in _text(MAKEFILE).splitlines():
        if line.startswith(".PHONY:"):
            return set(line.removeprefix(".PHONY:").split())
    return set()


def _declared_adrs() -> set[str]:
    """Every ADR id that has a heading in the log."""
    return {f"ADR-{number}" for number in ADR_HEADING.findall(_text(DECISION_LOG))}


def _cited_adrs(path: Path) -> set[str]:
    """Every ADR id a document cites."""
    return {f"ADR-{number}" for number in ADR_CITATION.findall(_text(path))}


def _rehearsal_region() -> str:
    """The text between the two rehearsal markers.

    Assumes the markers are well formed; `test_the_rehearsal_markers_are_one
    _well_formed_pair` is what proves that, and it is the test that fails first
    if they are not.
    """
    return _text(README).split(REHEARSAL_BEGIN)[1].split(REHEARSAL_END)[0]


def _rehearsal_commands() -> list[str]:
    """The command lines inside the rehearsal region's fenced blocks.

    Comments and blank lines dropped, because what the rehearsal runs is the
    commands. Only fenced blocks count - an inline span inside the region is
    prose formatting, not something the script is expected to execute.
    """
    return [
        line
        for block in FENCED_BLOCK.findall(_rehearsal_region())
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _human_ai_section() -> str:
    """The human/AI account, from its heading to the next `## ` heading."""
    text = _text(AI_WORKFLOW)
    start = text.index(HUMAN_AI_HEADING)
    rest = text[start + len(HUMAN_AI_HEADING) :]
    match = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: match.start()] if match else rest


def test_every_cited_adr_resolves_to_an_entry() -> None:
    """No document cites an ADR id the log does not define.

    The cheapest high-value check in this file. An id is four characters of
    prose that looks authoritative and can be wrong in a way no reader will
    catch: `ADR-096` for `ADR-069` reads perfectly and sends them to the wrong
    entry. Both citing documents are scanned, because `AI_WORKFLOW.md` carries
    more ADR references than the README does.
    """
    declared = _declared_adrs()
    offenders = {
        path.name: sorted(_cited_adrs(path) - declared)
        for path in (README, AI_WORKFLOW)
        if _cited_adrs(path) - declared
    }

    assert not offenders, (
        "These ADR ids are cited but have no `## ADR-NNN:` heading in "
        f"DECISION_LOG.md: {offenders}"
    )


def test_each_of_the_briefs_five_ambiguities_has_an_entry() -> None:
    """DOC-03's hardest clause, as a table rather than as a count.

    The requirement says the log records "every brief ambiguity resolved". A
    count cannot express that; five named questions can. This is deliberately
    the one hand-written table in the module - deriving it from the log would
    make the log's contents both the question and the answer.
    """
    declared = _declared_adrs()
    unresolved = {
        question: adr for question, adr in AMBIGUITY_ADRS.items() if adr not in declared
    }

    assert not unresolved, (
        "These of the brief's ambiguities point at an ADR that does not exist: "
        f"{unresolved}"
    )


def test_the_adr_count_the_readme_states_is_the_count_in_the_log() -> None:
    """The one number the README quotes about the log, pinned to the log.

    A count in prose is a number that was true once. This one is re-derived on
    every run, so appending an entry without touching the README is a red test
    and takes ten seconds to fix - which is the whole difference between a
    number that stays true and a number nobody dares touch.
    """
    stated = [int(n) for n in re.findall(r"\b(\d+) ADRs\b", _text(README))]
    actual = len(_declared_adrs())

    assert stated, "README.md states no ADR count; §Decisions is supposed to"
    assert set(stated) == {
        actual
    }, f"README.md says {stated} ADRs; DECISION_LOG.md has {actual} headings"


def test_the_contract_count_the_readme_states_is_the_count_in_importlinter() -> None:
    """Same rule, for the number of import-linter contracts."""
    stated = [int(n) for n in re.findall(r"\b(\d+) contracts\b", _text(README))]
    actual = len(
        [
            line
            for line in _text(IMPORTLINTER).splitlines()
            if line.startswith("[importlinter:contract")
        ]
    )

    assert stated, "README.md states no contract count; §Architecture is supposed to"
    assert set(stated) == {
        actual
    }, f"README.md says {stated} contracts; .importlinter declares {actual}"


def test_every_make_target_the_readme_names_exists() -> None:
    """A renamed target leaves the README telling the reader to type nothing.

    `make docker-test` is the single command this project asks an evaluator to
    run for the tests; if it is ever renamed, the README saying otherwise is a
    failed submission rather than a documentation nit.
    """
    declared = _phony_targets()
    offenders = sorted(_named_make_targets() - declared)

    assert not offenders, (
        f"README.md names these `make` targets, which are not on the Makefile's "
        f"`.PHONY` line ({sorted(declared)}): {offenders}"
    )


def test_the_endpoint_table_publishes_no_route_that_does_not_exist(
    spec: dict[str, Any],
) -> None:
    """One direction of the set equality: the README inventing an operation.

    Split from its opposite deliberately. The two failures have different causes
    and different fixes - a row here is a typo or a route that was removed, and
    a row missing is a route somebody added - and a single combined assertion
    would report them in one message that names both and explains neither.
    """
    invented = sorted(_documented_operations() - _published_operations(spec))

    assert not invented, (
        "README.md's endpoint table has rows for operations `app.openapi()` "
        f"does not publish: {invented}"
    )


def test_the_endpoint_table_omits_no_route_that_does_exist(
    spec: dict[str, Any],
) -> None:
    """The other direction, and the one that matters over time.

    A route added in some later phase, with no row here, leaves the README
    quietly incomplete - the failure mode a review habit never catches, because
    nobody re-reads a table they did not touch.
    """
    undocumented = sorted(_published_operations(spec) - _documented_operations())

    assert not undocumented, (
        "`app.openapi()` publishes these operations, and README.md's endpoint "
        f"table has no row for them: {undocumented}"
    )


def test_the_rehearsal_markers_are_one_well_formed_pair() -> None:
    """Exactly one of each, in order, with commands between them.

    *Exactly* one, not at least one - and that word is the whole point of this
    test. 06-REVIEW WR-05 recorded a marker guard in this repository that
    documented "exactly one" while enforcing "at least one"; a second `begin`
    would silently move the region and the rehearsal would execute a different
    set of commands than the one anybody reviewed. The same hole is not dug
    twice.
    """
    text = _text(README)
    begins = text.count(REHEARSAL_BEGIN)
    ends = text.count(REHEARSAL_END)

    assert (begins, ends) == (1, 1), (
        f"README.md has {begins} `{REHEARSAL_BEGIN}` and {ends} "
        f"`{REHEARSAL_END}`; exactly one of each is required"
    )
    assert text.index(REHEARSAL_BEGIN) < text.index(
        REHEARSAL_END
    ), f"`{REHEARSAL_END}` appears before `{REHEARSAL_BEGIN}` in README.md"

    commands = _rehearsal_commands()
    assert len(commands) >= MINIMUM_REHEARSAL_COMMANDS, (
        f"the rehearsal region holds {len(commands)} command line(s); at least "
        f"{MINIMUM_REHEARSAL_COMMANDS} are required for the region to be worth "
        "executing"
    )


def test_the_rehearsal_region_needs_no_virtualenv() -> None:
    """The region is run on a bare machine, so it may only name Docker targets.

    `make install` and every target that invokes `$(VENV)/bin/...` are host-path
    commands. The rehearsal clones into a temporary directory with no `.venv`,
    so a host-path target inside the markers would fail there for a reason that
    has nothing to do with the README being wrong.
    """
    docker_path_targets = {"env", "up", "down", "docker-test"}
    offenders = sorted(
        {
            target
            for block in FENCED_BLOCK.findall(_rehearsal_region())
            for target in MAKE_INVOCATION.findall(block)
        }
        - docker_path_targets
    )

    assert not offenders, (
        "these `make` targets appear inside the rehearsal markers but need a "
        f"host virtualenv: {offenders}"
    )


def test_neither_document_promises_anything_for_later() -> None:
    """Phase 7 is this phase; a promissory note in it is an unfinished file.

    `AI_WORKFLOW.md` carried `To be completed in Phase 7` markers from Phase 1
    onward, deliberately and visibly, rather than filler. They are gone, and
    this is what keeps them gone.
    """
    marker = "To be completed in Phase 7"
    offenders = [path.name for path in (README, AI_WORKFLOW) if marker in _text(path)]

    assert not offenders, f"`{marker}` still appears in: {offenders}"


def test_the_ai_workflow_still_draws_the_diagrams_aiw_01_asks_for() -> None:
    """AIW-01 is satisfied by pictures, so the pictures are counted.

    A floor rather than an equality, and fenced-block counting rather than
    rendering: there is no local Mermaid renderer and adding a Node toolchain to
    a Python deliverable is the wrong trade. Whether they *render* is a human
    look at the pushed page, which is a checkpoint in plan 07-05.
    """
    blocks = _text(AI_WORKFLOW).count("```mermaid")

    assert blocks >= MINIMUM_MERMAID_BLOCKS, (
        f"AI_WORKFLOW.md has {blocks} mermaid block(s); AIW-01 asks for the "
        f"workflow drawn, and at least {MINIMUM_MERMAID_BLOCKS} are expected"
    )


def test_the_human_ai_account_covers_every_phase() -> None:
    """AIW-02, as a totality over the seven phases that were actually run.

    Scoped to the section rather than the file: `Phase 3` appears a dozen times
    in the incident log, so a document-wide scan would report this section
    complete while it was still empty.
    """
    section = _human_ai_section()
    missing = [phase for phase in PHASES if f"Phase {phase}" not in section]

    assert not missing, (
        f"`{HUMAN_AI_HEADING}` in AI_WORKFLOW.md mentions no block for "
        f"phase(s): {missing}"
    )


def test_the_scan_is_not_vacuous() -> None:
    """Every parser in this module found something, and fails if it did not.

    The reason this is its own test and not an assertion tacked onto each check
    above: emptying `README.md` would otherwise make nine tests pass. Set
    difference against an empty set is empty, `count("```mermaid")` on missing
    text is not reached, and a `.PHONY` line that stopped being found returns an
    empty set that every target is trivially absent from - the gate would report
    perfect documentation about a file with nothing in it.

    It fails, it never skips. A skip here is the WR-06 shape: a green run that
    checked nothing, reported as a green run.
    """
    empty = [path.name for path in ROOT_DOCUMENTS if not path.is_file()]
    assert not empty, (
        f"these documents are missing: {empty}. In the container this means the "
        "Dockerfile `test` stage is not copying them (ADR-102)"
    )

    short = [path.name for path in ROOT_DOCUMENTS if len(_text(path).strip()) < 100]
    assert not short, f"these documents are effectively empty: {short}"

    rows = len(_documented_operations())
    assert rows >= MINIMUM_ENDPOINT_ROWS, (
        f"the endpoint-table parser found {rows} row(s) in README.md; at least "
        f"{MINIMUM_ENDPOINT_ROWS} are expected"
    )

    for path in (README, AI_WORKFLOW):
        citations = len(_cited_adrs(path))
        assert citations >= MINIMUM_ADR_CITATIONS, (
            f"the ADR scanner found {citations} citation(s) in {path.name}; at "
            f"least {MINIMUM_ADR_CITATIONS} are expected"
        )

    targets = len(_phony_targets())
    assert targets >= MINIMUM_PHONY_TARGETS, (
        f"the `.PHONY` parser found {targets} target(s) in the Makefile; at "
        f"least {MINIMUM_PHONY_TARGETS} are expected"
    )

    assert (
        _declared_adrs()
    ), "the ADR-heading parser found no entries in DECISION_LOG.md"
    assert _human_ai_section().strip(), f"`{HUMAN_AI_HEADING}` is empty"
