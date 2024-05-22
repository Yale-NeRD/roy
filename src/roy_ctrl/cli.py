# cli.py
import click
import roy_ctrl
rust_lib = roy_ctrl.RustLib()

@click.group()
def cli():
    pass

@cli.command()
def start():
    """Start the daemon."""
    rust_lib.start_daemon()
    click.echo("Daemon started.")

@cli.command()
def stop():
    """Stop the daemon."""
    rust_lib.stop_daemon()
    click.echo("Daemon stopped.")

@cli.command()
def status():
    """Check the status of the daemon."""
    if rust_lib.is_running():
        click.echo("Daemon is running.")
    else:
        click.echo("Daemon is stopped.")

if __name__ == '__main__':
    cli()
