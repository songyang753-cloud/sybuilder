#!/usr/bin/env python3
"""Structured SVG checks used by validate-svg.sh.

The validator intentionally uses only the Python standard library so it works
inside a freshly installed skill without adding another runtime dependency.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence


NUMBER_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
PATH_TOKEN_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
URL_REF_RE = re.compile(r"url\(\s*#([^\s)]+)\s*\)")
MARKER_ATTRIBUTES = ("marker-start", "marker-mid", "marker-end")
EXCLUDED_ROLES = {"background", "container", "decoration", "label", "legend"}
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

Point = tuple[float, float]
Matrix = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class Bounds:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class Collision:
    edge: str
    obstacle: str


@dataclass(frozen=True)
class ElementContext:
    element: ET.Element
    matrix: Matrix
    role: Optional[str]
    in_defs: bool


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_number(value: Optional[str], default: Optional[float] = 0.0) -> Optional[float]:
    if value is None:
        return default
    match = NUMBER_RE.match(value.strip())
    if not match:
        return default
    return float(match.group(0))


def multiply(left: Matrix, right: Matrix) -> Matrix:
    a1, b1, c1, d1, e1, f1 = left
    a2, b2, c2, d2, e2, f2 = right
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def transform_point(matrix: Matrix, point: Point) -> Point:
    a, b, c, d, e, f = matrix
    x, y = point
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(value: Optional[str]) -> Matrix:
    result = IDENTITY
    if not value:
        return result
    for name, raw_values in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", value):
        values = [float(item) for item in NUMBER_RE.findall(raw_values)]
        name = name.lower()
        current = IDENTITY
        if name == "matrix" and len(values) == 6:
            current = tuple(values)  # type: ignore[assignment]
        elif name == "translate" and values:
            current = (1, 0, 0, 1, values[0], values[1] if len(values) > 1 else 0)
        elif name == "scale" and values:
            current = (values[0], 0, 0, values[1] if len(values) > 1 else values[0], 0, 0)
        elif name == "rotate" and values:
            angle = math.radians(values[0])
            rotation = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle), 0, 0)
            if len(values) >= 3:
                cx, cy = values[1], values[2]
                current = multiply(
                    multiply((1, 0, 0, 1, cx, cy), rotation),
                    (1, 0, 0, 1, -cx, -cy),
                )
            else:
                current = rotation
        result = multiply(result, current)
    return result


def infer_role(element: ET.Element, inherited: Optional[str]) -> Optional[str]:
    explicit = element.get("data-graph-role")
    if explicit:
        return explicit.strip().lower()
    identity = " ".join(filter(None, (element.get("id"), element.get("class")))).lower()
    if any(token in identity for token in ("legend", "key-box", "key_box")):
        return "legend"
    if local_name(element.tag) == "g":
        text = " ".join("".join(child.itertext()) for child in element if local_name(child.tag) == "text").lower()
        if "legend" in text:
            return "legend"
    return inherited


def walk(element: ET.Element, matrix: Matrix = IDENTITY, role: Optional[str] = None, in_defs: bool = False) -> Iterator[ElementContext]:
    current_matrix = multiply(matrix, parse_transform(element.get("transform")))
    current_role = infer_role(element, role)
    current_in_defs = in_defs or local_name(element.tag) == "defs"
    yield ElementContext(element, current_matrix, current_role, current_in_defs)
    child_role = current_role if current_role in {"background", "decoration", "label", "legend", "node"} else None
    for child in element:
        yield from walk(child, current_matrix, child_role, current_in_defs)


def canvas_size(root: ET.Element) -> Point:
    values = [float(item) for item in NUMBER_RE.findall(root.get("viewBox", ""))]
    if len(values) == 4:
        return values[2], values[3]
    return (
        float(parse_number(root.get("width"), 0.0) or 0.0),
        float(parse_number(root.get("height"), 0.0) or 0.0),
    )


def bounds_from_points(points: Sequence[Point]) -> Optional[Bounds]:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def transformed_bounds(matrix: Matrix, points: Sequence[Point]) -> Optional[Bounds]:
    return bounds_from_points([transform_point(matrix, point) for point in points])


def shape_bounds(context: ElementContext, canvas: Point) -> Optional[Bounds]:
    element = context.element
    tag = local_name(element.tag)
    role = context.role
    if context.in_defs or role in EXCLUDED_ROLES:
        return None

    if tag == "rect":
        x = float(parse_number(element.get("x"), 0.0) or 0.0)
        y = float(parse_number(element.get("y"), 0.0) or 0.0)
        width = parse_number(element.get("width"), None)
        height = parse_number(element.get("height"), None)
        if width is None or height is None or width <= 0 or height <= 0:
            return None
        canvas_width, canvas_height = canvas
        if role != "node":
            if element.get("x") is None and element.get("y") is None:
                return None
            if height <= 28 or width <= 8:
                return None
            nearly_canvas = canvas_width > 0 and canvas_height > 0 and width >= canvas_width * 0.9 and height >= canvas_height * 0.9
            if nearly_canvas:
                return None
            container_like = bool(element.get("stroke-dasharray")) or element.get("fill", "").strip().lower() == "none"
            if container_like and (
                (canvas_width > 0 and width >= canvas_width * 0.45)
                or (canvas_height > 0 and height >= canvas_height * 0.45)
            ):
                return None
        return transformed_bounds(
            context.matrix,
            ((x, y), (x + width, y), (x + width, y + height), (x, y + height)),
        )

    if tag in {"circle", "ellipse"}:
        cx = float(parse_number(element.get("cx"), 0.0) or 0.0)
        cy = float(parse_number(element.get("cy"), 0.0) or 0.0)
        rx = float(parse_number(element.get("r") or element.get("rx"), 0.0) or 0.0)
        ry = float(parse_number(element.get("r") or element.get("ry"), 0.0) or 0.0)
        if rx < 12 or ry < 12:
            return None
        return transformed_bounds(
            context.matrix,
            ((cx - rx, cy - ry), (cx + rx, cy - ry), (cx + rx, cy + ry), (cx - rx, cy + ry)),
        )

    if tag in {"polygon", "polyline"} and not has_marker(element):
        values = [float(item) for item in NUMBER_RE.findall(element.get("points", ""))]
        points = list(zip(values[::2], values[1::2]))
        if len(points) < 3:
            return None
        return transformed_bounds(context.matrix, points)
    return None


def has_marker(element: ET.Element) -> bool:
    return any(element.get(attribute) for attribute in MARKER_ATTRIBUTES)


def marker_references(root: ET.Element) -> tuple[set[str], set[str]]:
    definitions = {
        element.get("id", "")
        for element in root.iter()
        if local_name(element.tag) == "marker" and element.get("id")
    }
    references: set[str] = set()
    for element in root.iter():
        for attribute in MARKER_ATTRIBUTES:
            value = element.get(attribute, "")
            references.update(URL_REF_RE.findall(value))
    return definitions, references


def sample_quadratic(start: Point, control: Point, end: Point, steps: int = 12) -> list[Point]:
    return [
        (
            (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t**2 * end[0],
            (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t**2 * end[1],
        )
        for t in (index / steps for index in range(1, steps + 1))
    ]


def sample_cubic(start: Point, first: Point, second: Point, end: Point, steps: int = 16) -> list[Point]:
    return [
        (
            (1 - t) ** 3 * start[0] + 3 * (1 - t) ** 2 * t * first[0] + 3 * (1 - t) * t**2 * second[0] + t**3 * end[0],
            (1 - t) ** 3 * start[1] + 3 * (1 - t) ** 2 * t * first[1] + 3 * (1 - t) * t**2 * second[1] + t**3 * end[1],
        )
        for t in (index / steps for index in range(1, steps + 1))
    ]


def path_points(path_data: str) -> list[Point]:
    tokens = PATH_TOKEN_RE.findall(path_data or "")
    points: list[Point] = []
    index = 0
    command = ""
    current = (0.0, 0.0)
    start = current
    previous_cubic: Optional[Point] = None
    previous_quadratic: Optional[Point] = None

    def read(count: int) -> Optional[list[float]]:
        nonlocal index
        if index + count > len(tokens) or any(re.fullmatch(r"[A-Za-z]", token) for token in tokens[index : index + count]):
            return None
        values = [float(token) for token in tokens[index : index + count]]
        index += count
        return values

    def absolute(x: float, y: float, relative: bool) -> Point:
        return (current[0] + x, current[1] + y) if relative else (x, y)

    while index < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[index]):
            command = tokens[index]
            index += 1
        if not command:
            return []
        relative = command.islower()
        op = command.upper()
        if op == "Z":
            if current != start:
                points.append(start)
            current = start
            previous_cubic = previous_quadratic = None
            command = ""
            continue
        count = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}.get(op)
        if count is None:
            return []
        values = read(count)
        if values is None:
            return []

        if op == "M":
            current = absolute(values[0], values[1], relative)
            start = current
            points.append(current)
            command = "l" if relative else "L"
        elif op == "L":
            current = absolute(values[0], values[1], relative)
            points.append(current)
        elif op == "H":
            current = (current[0] + values[0], current[1]) if relative else (values[0], current[1])
            points.append(current)
        elif op == "V":
            current = (current[0], current[1] + values[0]) if relative else (current[0], values[0])
            points.append(current)
        elif op == "C":
            first = absolute(values[0], values[1], relative)
            second = absolute(values[2], values[3], relative)
            end = absolute(values[4], values[5], relative)
            points.extend(sample_cubic(current, first, second, end))
            current, previous_cubic = end, second
            previous_quadratic = None
        elif op == "S":
            first = (2 * current[0] - previous_cubic[0], 2 * current[1] - previous_cubic[1]) if previous_cubic else current
            second = absolute(values[0], values[1], relative)
            end = absolute(values[2], values[3], relative)
            points.extend(sample_cubic(current, first, second, end))
            current, previous_cubic = end, second
            previous_quadratic = None
        elif op == "Q":
            control = absolute(values[0], values[1], relative)
            end = absolute(values[2], values[3], relative)
            points.extend(sample_quadratic(current, control, end))
            current, previous_quadratic = end, control
            previous_cubic = None
        elif op == "T":
            control = (2 * current[0] - previous_quadratic[0], 2 * current[1] - previous_quadratic[1]) if previous_quadratic else current
            end = absolute(values[0], values[1], relative)
            points.extend(sample_quadratic(current, control, end))
            current, previous_quadratic = end, control
            previous_cubic = None
        elif op == "A":
            # Arc endpoints are exact; a chord is a conservative collision check.
            current = absolute(values[5], values[6], relative)
            points.append(current)
            previous_cubic = previous_quadratic = None
        if op not in {"C", "S", "Q", "T"}:
            previous_cubic = previous_quadratic = None
    return points


def edge_points(context: ElementContext) -> list[Point]:
    element = context.element
    tag = local_name(element.tag)
    if context.in_defs or context.role in {"background", "decoration", "label", "legend", "node"} or not has_marker(element):
        return []
    if tag == "line":
        points = [
            (float(parse_number(element.get("x1"), 0.0) or 0.0), float(parse_number(element.get("y1"), 0.0) or 0.0)),
            (float(parse_number(element.get("x2"), 0.0) or 0.0), float(parse_number(element.get("y2"), 0.0) or 0.0)),
        ]
    elif tag == "polyline":
        values = [float(item) for item in NUMBER_RE.findall(element.get("points", ""))]
        points = list(zip(values[::2], values[1::2]))
    elif tag == "path":
        points = path_points(element.get("d", ""))
    else:
        return []
    return [transform_point(context.matrix, point) for point in points]


def segment_hits_bounds(start: Point, end: Point, bounds: Bounds, epsilon: float = 1e-5) -> bool:
    left, right = bounds.left + epsilon, bounds.right - epsilon
    top, bottom = bounds.top + epsilon, bounds.bottom - epsilon
    if left >= right or top >= bottom:
        return False
    x1, y1 = start
    dx, dy = end[0] - x1, end[1] - y1
    low, high = 0.0, 1.0
    for p, q in ((-dx, x1 - left), (dx, right - x1), (-dy, y1 - top), (dy, bottom - y1)):
        if abs(p) < epsilon:
            if q < 0:
                return False
            continue
        ratio = q / p
        if p < 0:
            low = max(low, ratio)
        else:
            high = min(high, ratio)
        if low > high:
            return False
    return high - low > epsilon and high > epsilon and low < 1 - epsilon


def points_within_bounds(points: Sequence[Point], bounds: Bounds, epsilon: float = 1e-5) -> bool:
    return bool(points) and all(
        bounds.left - epsilon <= x <= bounds.right + epsilon
        and bounds.top - epsilon <= y <= bounds.bottom + epsilon
        for x, y in points
    )


def find_collisions(root: ET.Element) -> list[Collision]:
    contexts = list(walk(root))
    obstacles = [
        (context, bounds)
        for context in contexts
        if (bounds := shape_bounds(context, canvas_size(root))) is not None
    ]
    edges = [(context, edge_points(context)) for context in contexts]
    legend_bounds = {
        bounds
        for _, bounds in obstacles
        if sum(points_within_bounds(points, bounds) for _, points in edges if len(points) >= 2) >= 2
    }
    obstacles = [(context, bounds) for context, bounds in obstacles if bounds not in legend_bounds]
    collisions: list[Collision] = []
    for edge_context, points in edges:
        if len(points) < 2:
            continue
        if any(points_within_bounds(points, bounds) for bounds in legend_bounds):
            continue
        edge = edge_context.element
        for obstacle_context, bounds in obstacles:
            obstacle = obstacle_context.element
            if any(segment_hits_bounds(first, second, bounds) for first, second in zip(points, points[1:])):
                collisions.append(
                    Collision(
                        describe_element(edge),
                        describe_element(obstacle),
                    )
                )
                break
    return collisions


def describe_element(element: ET.Element) -> str:
    tag = local_name(element.tag)
    if element.get("id"):
        return f"{tag}#{element.get('id')}"
    if tag == "path":
        path_data = re.sub(r"\s+", " ", element.get("d", "")).strip()
        return f"path[d={path_data[:72]}]"
    attributes = []
    for name in ("x", "y", "width", "height", "cx", "cy", "r", "rx", "ry"):
        if element.get(name) is not None:
            attributes.append(f"{name}={element.get(name)}")
    return f"{tag}[{' '.join(attributes)}]" if attributes else tag


def parse_svg(path: Path) -> ET.Element:
    return ET.parse(path).getroot()


def run_check(path: Path, check: str) -> tuple[bool, list[str]]:
    try:
        root = parse_svg(path)
    except (ET.ParseError, OSError) as error:
        return False, [str(error)]
    if check == "xml":
        return True, []
    if check == "markers":
        definitions, references = marker_references(root)
        missing = sorted(references - definitions)
        return not missing, [f"missing marker: {marker}" for marker in missing]
    collisions = find_collisions(root)
    details = [
        f"{item.edge} intersects {item.obstacle}"
        for item in collisions
    ]
    return not collisions, details


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg_file", type=Path)
    parser.add_argument("--check", choices=("xml", "markers", "collisions"), required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ok, details = run_check(args.svg_file, args.check)
    for detail in details:
        print(detail)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
