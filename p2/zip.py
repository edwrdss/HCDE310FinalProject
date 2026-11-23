# AI-written
import requests

ZIP_URL = "https://api.zippopotam.us/us/{zip_code}"  # free, no API key


def zip_to_coordinates(zip_code: str) -> dict:
    """Convert a US ZIP code to coordinates and place info.

    Returns: {"zip", "city", "state", "latitude", "longitude"}
    Raises:  ValueError for malformed or unknown ZIP codes.
    """
    zip_code = str(zip_code).strip()
    if not (len(zip_code) == 5 and zip_code.isdigit()):
        raise ValueError(f"ZIP code must be 5 digits, got: {zip_code!r}")

    resp = requests.get(ZIP_URL.format(zip_code=zip_code), timeout=10)
    if resp.status_code == 404:
        raise ValueError(f"Unknown ZIP code: {zip_code}")
    resp.raise_for_status()

    data = resp.json()
    place = data["places"][0]
    return {
        "zip": data["post code"],
        "city": place["place name"],
        "state": place["state abbreviation"],
        "latitude": float(place["latitude"]),
        "longitude": float(place["longitude"]),
    }


def _close(actual: float, expected: float, tol: float = 0.05) -> bool:
    # 0.05 degrees is roughly 3 miles
    return abs(actual - expected) <= tol


def run_checks():
    checks = [
        # (zip, expected_lat, expected_lon)
        ("94611", 37.83191, -122.21592),   # Oakland, CA
        ("98105", 47.6615, -122.2811),     # Seattle, WA
    ]
    for zip_code, exp_lat, exp_lon in checks:
        result = zip_to_coordinates(zip_code)
        ok = _close(result["latitude"], exp_lat) and _close(result["longitude"], exp_lon)
        print(
            f"{'PASS' if ok else 'FAIL'} {zip_code} ({result['city']}, {result['state']}): "
            f"got ({result['latitude']}, {result['longitude']}), "
            f"expected ~({exp_lat}, {exp_lon})"
        )


if __name__ == "__main__":
    run_checks()

"""
PASS 94611 (Oakland, CA): got (37.83191, -122.21592), expected ~(37.83191, -122.21592)
PASS 98105 (Seattle, WA): got (47.6615, -122.2811), expected ~(47.6615, -122.2811)
"""