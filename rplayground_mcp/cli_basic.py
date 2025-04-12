import asyncio
import argparse

from .session_manager import SessionManager
import sys
import logging

sm = SessionManager()


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Predefined graphics test command
GRAPHICS_TEST_COMMAND = """\
# First request commands:

# Create sample data
set.seed(123)
groups <- factor(rep(LETTERS[1:4], each = 10))
values <- c(rnorm(10, mean = 5, sd = 1),   # Group A
            rnorm(10, mean = 6, sd = 1),   # Group B
            rnorm(10, mean = 5.5, sd = 1), # Group C
            rnorm(10, mean = 7, sd = 1))   # Group D

# Fit ANOVA model
model <- aov(values ~ groups)

# Summary of the ANOVA
summary(model)

# Basic pairwise comparisons
pairwise.t.test(values, groups, p.adjust.method = "none")

# Multiple comparison procedures
# 1. Bonferroni correction
pairwise.t.test(values, groups, p.adjust.method = "bonferroni")

# 2. Tukey's Honest Significant Difference
TukeyHSD(model)

# 3. Visual representation of Tukey's HSD
plot_data <- TukeyHSD(model)
par(mar = c(5, 8, 4, 2))
plot(plot_data, las = 1)
"""


async def main():
    parser = argparse.ArgumentParser(
        description="Execute R commands in a temporary session."
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="The R command to execute. If omitted and --graphicstest is not used, help is shown.",
        default=None,
    )
    parser.add_argument(
        "--graphicstest",
        action="store_true",
        help="Run a predefined graphics test command instead of the provided command.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for user input after execution before destroying the session.",
    )

    args = parser.parse_args()

    command_to_execute: str | None = None

    if args.graphicstest:
        command_to_execute = GRAPHICS_TEST_COMMAND
    elif args.command:
        command_to_execute = args.command
    else:
        parser.print_help()
        sys.exit(1)

    id = await sm.create_session()
    print(f"Created session {id}")
    try:
        assert command_to_execute is not None
        result = await sm.execute_in_session(id, command_to_execute)
        print(f"Result: {result}")

        if args.wait:
            input("Press Enter to destroy the session...")

    finally:
        await sm.destroy_session(id)
        print(f"Destroyed session {id}")


def run():
    print("Starting R command execution CLI")
    asyncio.run(main())


if __name__ == "__main__":
    run()
