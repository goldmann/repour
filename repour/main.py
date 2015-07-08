import argparse
import logging
import os
import sys

import yaml

from . import validation

logger = logging.getLogger(__name__)

def override(config, config_coords, args, arg_name):
    if getattr(args, arg_name, None) is not None:
        def resolve_leaf_dict(parent_dict, leaf_coords):
            if len(leaf_coords) == 1:
                return parent_dict
            return resolve_leaf_dict(parent_dict[leaf_coords[0]], leaf_coords[1:])
        d = resolve_leaf_dict(config, config_coords)
        logger.debug("Overriding config/{} with arg {}".format("/".join(config_coords), arg_name))
        d[config_coords[-1]] = getattr(args, arg_name)

#
# Subcommands
#

def run_subcommand(args, config):
    from . import server

    override(config, ("bind", "address"), args, "address")
    override(config, ("bind", "port"), args, "port")
    server.start_server(
        bind=config["bind"],
        repo_provider=config["repo_provider"],
    )

#
# General
#

def create_argparser():
    parser = argparse.ArgumentParser(description="Run repour server in various modes")
    parser.add_argument("-c", "--config", default="config.yaml", help="Path to the configuration file. Default: config.yaml")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase logging verbosity one level, repeatable.")
    parser.add_argument("-q", "--quiet", action="count", default=0, help="Decrease logging verbosity one level, repeatable.")
    parser.add_argument("-s", "--silent", action="store_true", help="Do not log to stdio.")
    parser.add_argument("-l", "--log", help="Override the path for the log file provided in the config file.")

    subparsers = parser.add_subparsers()

    run_desc = "Run the server"
    run_parser = subparsers.add_parser("run", help=run_desc)
    run_parser.description = run_desc
    run_parser.set_defaults(func=run_subcommand)
    run_parser.add_argument("-a", "--address", help="Override the bind IP address provided in the config file.")
    run_parser.add_argument("-p", "--port", help="Override the bind port number provided in the config file.")

    return parser

def configure_logging(log_path, default_level, verbose_count, quiet_count, silent):
    formatter = logging.Formatter(
        fmt="{asctime} {levelname} {name}:{lineno} {message}",
        style="{",
    )

    root_logger = logging.getLogger()

    file_log = logging.FileHandler(log_path)
    file_log.setFormatter(formatter)
    root_logger.addHandler(file_log)

    if not silent:
        console_log = logging.StreamHandler()
        console_log.setFormatter(formatter)
        root_logger.addHandler(console_log)

    log_level = default_level + (10 * quiet_count) - (10 * verbose_count)
    root_logger.setLevel(log_level)

def load_config(config_path):
    config_dir = os.path.dirname(config_path)
    def config_relative(loader, node):
        value = loader.construct_scalar(node)
        return os.path.normpath(os.path.join(config_dir, value))
    yaml.add_constructor("!config_relative", config_relative)

    with open(config_path, "r") as f:
        config = yaml.load(f)

    return validation.server_config(config)

def main():
    # Args
    parser = create_argparser()
    args = parser.parse_args()

    # Config
    config = load_config(args.config)

    # Logging
    override(config, ("log", "path"), args, "log")
    log_default_level = logging._nameToLevel[config["log"]["level"]]
    configure_logging(config["log"]["path"], log_default_level, args.verbose, args.quiet, args.silent)

    if "func" in args:
        sys.exit(args.func(args, config))
    else:
        parser.print_help()
        sys.exit(1)