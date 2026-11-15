"""Network metric: bytes received and sent."""


def parse_net(text):
    rx = tx = 0
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        if name.strip() == "lo":
            continue
        v = data.split()
        if len(v) >= 9:
            rx += int(v[0])
            tx += int(v[8])
    return rx, tx
