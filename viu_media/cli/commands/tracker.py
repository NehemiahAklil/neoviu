from typing import TYPE_CHECKING, List, Optional, cast

import click

if TYPE_CHECKING:
    from ...core.config import AppConfig
    from ...libs.selectors.base import BaseSelector
    from ..service.feedback import FeedbackService
    from ..service.tracking import TrackingService
    from ..service.tracking.service import RemoteMode

SITES = ("anilist", "myanimelist")
MODES = ("anilist", "myanimelist", "both", "none")


def _services(
    config: "AppConfig",
) -> "tuple[TrackingService, BaseSelector, FeedbackService]":
    from ...libs.selectors.selector import create_selector
    from ..service.feedback import FeedbackService
    from ..service.tracking import TrackingService

    return TrackingService(config), create_selector(config), FeedbackService(config)


def _print_status(tracking: "TrackingService", feedback: "FeedbackService") -> None:
    from rich.console import Console
    from rich.table import Table

    from ..service.tracking import TRACKER_LABELS

    with feedback.progress("Checking trackers", transient=True):
        states = tracking.states()
        source = tracking.list_source

    table = Table(title="Anime trackers", title_justify="left")
    table.add_column("Tracker")
    table.add_column("Syncing")
    table.add_column("Account")
    for state in states:
        if state.logged_in:
            account = f"[green]{state.username or 'logged in'}[/]"
        elif state.username:
            account = f"[yellow]{state.username} (session expired)[/]"
        else:
            account = "[dim]not logged in[/]"
        table.add_row(
            state.label, "[green]yes[/]" if state.enabled else "[dim]no[/]", account
        )

    console = Console()
    console.print(table)
    console.print(f"Mode: [bold]{tracking.remote}[/]")
    if source:
        console.print(f"Your lists come from {TRACKER_LABELS[source]}.")
    elif tracking.enabled_trackers:
        console.print("Run [bold]nviu tracker login[/] to connect your account.")
    else:
        console.print(
            "Progress is only tracked locally. "
            "Run [bold]nviu tracker login[/] to sync it with AniList or MyAnimeList."
        )
    if tracking.is_enabled("myanimelist") and not tracking.mal_client_id:
        console.print(
            "[yellow]MyAnimeList needs your own client ID; "
            "'nviu tracker login myanimelist' walks you through it.[/]"
        )


@click.group(
    invoke_without_command=True,
    help=(
        "Connect AniList and/or MyAnimeList so your lists show up in nviu and "
        "your watch progress is synced to the sites. Shows the current status "
        "when run without a subcommand."
    ),
    short_help="Manage AniList/MyAnimeList tracking",
)
@click.pass_context
def tracker(ctx: click.Context):
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@tracker.command(help="Show which trackers are enabled and logged in.")
@click.pass_obj
def status(config: "AppConfig"):
    tracking, _, feedback = _services(config)
    _print_status(tracking, feedback)


@tracker.command(
    help=(
        "Log in to a tracker through your browser. Without SITE, logs in to "
        "every enabled tracker, asking where to track first if nothing is enabled."
    )
)
@click.argument("site", type=click.Choice(SITES), required=False)
@click.option("--token", help="AniList access token (skips opening the browser).")
@click.option("--client-id", help="Your MyAnimeList API client ID.")
@click.option(
    "--client-secret", default="", help="Your MyAnimeList API client secret, if any."
)
@click.pass_context
def login(
    ctx: click.Context,
    site: Optional[str],
    token: Optional[str],
    client_id: Optional[str],
    client_secret: str,
):
    from ..service.tracking import ANILIST, TRACKER_LABELS
    from ..utils.tracker_login import choose_remote, login_anilist, login_myanimelist

    tracking, selector, feedback = _services(ctx.obj)
    if client_id:
        tracking.set_mal_credentials(client_id, client_secret)
        feedback.success("Saved your MyAnimeList client ID.")

    targets: List[str]
    if site:
        targets = [site]
    else:
        if not tracking.enabled_trackers:
            feedback.info("Progress is only tracked locally right now.")
            if not choose_remote(tracking, selector, feedback):
                return
        targets = tracking.missing_logins()
        if not targets:
            if tracking.enabled_trackers:
                feedback.success("You are already logged in to every enabled tracker.")
            return

    if token and ANILIST not in targets:
        feedback.warning("--token only applies to AniList and was ignored.")

    failed = False
    for target in targets:
        if target == ANILIST:
            ok = login_anilist(tracking, selector, feedback, token)
        else:
            ok = login_myanimelist(tracking, selector, feedback)
        failed = failed or not ok
        if ok and not tracking.is_enabled(target):
            label = TRACKER_LABELS[target]
            if selector.confirm(f"Sync your progress to {label}?", default=True):
                remote = cast(
                    "RemoteMode", target if not tracking.enabled_trackers else "both"
                )
                tracking.set_remote(remote)
                feedback.success(f"Tracking mode set to '{remote}'.")
            else:
                feedback.info(f"Run 'nviu tracker mode {target}' to sync with {label}.")
    if failed:
        ctx.exit(1)


@tracker.command(help="Log out of a tracker (both by default).")
@click.argument("site", type=click.Choice((*SITES, "all")), default="all")
@click.pass_obj
def logout(config: "AppConfig", site: str):
    from ..service.tracking import TRACKER_LABELS

    tracking, _, feedback = _services(config)
    for target in SITES if site == "all" else (site,):
        tracking.logout(target)
        feedback.success(f"Logged out of {TRACKER_LABELS[target]}.")


@tracker.command(
    help=(
        "Choose where progress is synced: anilist, myanimelist, both, or none "
        "(local only). Asks interactively when MODE is omitted."
    )
)
@click.argument("mode", type=click.Choice(MODES), required=False)
@click.pass_obj
def mode(config: "AppConfig", mode: Optional[str]):
    from ..service.tracking import TRACKER_LABELS
    from ..utils.tracker_login import choose_remote

    tracking, selector, feedback = _services(config)
    if mode is None:
        choose_remote(tracking, selector, feedback)
        return
    tracking.set_remote(cast("RemoteMode", mode))
    feedback.success(f"Tracking mode set to '{mode}'.")
    if missing := tracking.missing_logins():
        labels = " and ".join(TRACKER_LABELS[t] for t in missing)
        feedback.info(f"Run 'nviu tracker login' to connect {labels}.")
