import directives


def count(source: str) -> int:
    return sum(
        1
        for line in source.splitlines()
        if line.lstrip().startswith("#") and not directives.is_directive(line, "hash")
    )
