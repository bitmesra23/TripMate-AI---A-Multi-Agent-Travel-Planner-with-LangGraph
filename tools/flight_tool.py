import os
import re
import certifi
import airportsdata
import pycountry
import requests

from dotenv import load_dotenv

# ============================================================
# 1. ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "DAC").upper()

BASE_URL = "https://api.aviationstack.com/v1/flights"

AIRPORTS = airportsdata.load("IATA")


# ============================================================
# 2. COUNTRY ALIASES
# ============================================================

COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "great britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}


# ============================================================
# 3. CITY PREFERRED AIRPORTS
# ============================================================

CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}


# ============================================================
# 4. COUNTRY PREFERRED AIRPORTS
# ============================================================

COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "SG": "SIN",
    "AE": "DXB",
    "GB": "LHR",
    "US": "JFK",
    "KR": "ICN",
    "CN": "PEK",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
    "RU": "SVO",
    "VN": "SGN",
}


# ============================================================
# 5. TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:

    text = text.lower().strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    stop_words = [
        "flight", "flights",
        "ticket", "tickets",
        "trip", "travel",
        "plan", "complete",
        "days", "day",
        "including", "hotel",
        "hotels", "sightseeing",
        "under", "budget",
        "info", "information"
    ]

    words = [
        word for word in text.split()
        if word not in stop_words
    ]

    return " ".join(words).strip()


# ============================================================
# 6. COUNTRY NAME TO COUNTRY CODE
# ============================================================

def country_name_to_code(text: str):

    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2

    except LookupError:
        pass

    # Detect country name inside longer text

    for country in pycountry.countries:

        country_name = country.name.lower()

        if country_name in text:
            return country.alpha_2

    # Check aliases

    for alias, code in COUNTRY_ALIASES.items():

        if re.search(
            rf"\b{re.escape(alias)}\b",
            text
        ):
            return code

    return None


# ============================================================
# 7. AIRPORT COUNTRY MATCHING
# ============================================================

def airport_country_matches(
    airport: dict,
    country_code: str
) -> bool:

    airport_country = str(
        airport.get("country", "")
    ).upper().strip()

    if airport_country == country_code:
        return True

    try:

        country = pycountry.countries.get(
            alpha_2=country_code
        )

        if country and (
            airport_country.lower() == country.name.lower()
        ):
            return True

    except Exception:
        pass

    return False


# ============================================================
# 8. GET BEST AIRPORT FOR COUNTRY
# ============================================================

def get_best_airport_for_country(country_code: str):

    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    for iata, airport in AIRPORTS.items():

        if not iata:
            continue

        if airport_country_matches(airport, country_code):

            name = str(
                airport.get("name", "")
            ).lower()

            city = str(
                airport.get("city", "")
            ).lower()

            score = 0

            if "international" in name:
                score += 50

            if "intl" in name:
                score += 40

            if "capital" in name:
                score += 20

            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)

    return candidates[0][1]


# ============================================================
# 9. RESOLVE LOCATION TO IATA
# ============================================================

def resolve_location_to_iata(location: str):
    """
    Converts country, city, airport or IATA code into IATA.

    Examples:
        Bangladesh -> DAC
        Japan      -> NRT
        Dhaka      -> DAC
        Tokyo      -> NRT
        DAC        -> DAC
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code

    if re.fullmatch(r"[A-Za-z]{3}", raw_location):

        code = raw_location.upper()

        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # Preferred city airport

    if location_clean in CITY_MAIN_AIRPORT:

        code = CITY_MAIN_AIRPORT[location_clean]

        if code in AIRPORTS:
            return code

    # Country airport

    country_code = country_name_to_code(location_clean)

    if country_code:

        airport = get_best_airport_for_country(
            country_code
        )

        if airport:
            return airport

    # Exact city match from airport database

    city_matches = []

    for iata, airport in AIRPORTS.items():

        city = str(
            airport.get("city", "")
        ).lower().strip()

        name = str(
            airport.get("name", "")
        ).lower().strip()

        score = 0

        if city == location_clean:
            score += 100

        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:

        city_matches.sort(reverse=True)

        return city_matches[0][1]

    return None


# ============================================================
# 10. FIND LOCATION MENTIONS
# ============================================================

def find_location_mentions(query: str):
    """
    Finds country or city names inside natural language queries.
    """

    q = query.lower()

    mentions = []

    # Country aliases

    for alias in COUNTRY_ALIASES:

        if re.search(
            rf"\b{re.escape(alias)}\b",
            q
        ):
            mentions.append(alias)

    # Country names from pycountry

    for country in pycountry.countries:

        name = country.name.lower()

        if len(name) >= 4 and re.search(
            rf"\b{re.escape(name)}\b",
            q
        ):
            mentions.append(name)

    # Preferred city names

    for city in CITY_MAIN_AIRPORT:

        if re.search(
            rf"\b{re.escape(city)}\b",
            q
        ):
            mentions.append(city)

    # Remove duplicates while preserving order

    unique_mentions = list(dict.fromkeys(mentions))

    # Prefer longer names over their overlapping shorter names

    unique_mentions.sort(
        key=len,
        reverse=True
    )

    return unique_mentions


# ============================================================
# 11. PARSE FLIGHT ROUTE
# ============================================================

def parse_route(query: str):
    """
    Extracts departure and arrival IATA codes.

    Supported queries:

    1. From Bangladesh to Japan
    2. To Japan from Bangladesh
    3. Flights from Mumbai
    4. Flights to Singapore
    5. Japan trip from Bangladesh
    6. Bangladesh to Japan
    7. DAC to NRT
    8. Global flights

    Returns:
        dep_iata, arr_iata
    """

    q = query.strip()
    q_lower = q.lower()

    # Global flight queries

    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(
        keyword in q_lower
        for keyword in global_keywords
    ):
        return None, None

    # Direct IATA route

    codes = re.findall(
        r"\b[A-Z]{3}\b",
        q
    )

    valid_codes = [
        code.upper()
        for code in codes
        if code.upper() in AIRPORTS
    ]

    if len(valid_codes) >= 2:

        return valid_codes[0], valid_codes[1]

    # Pattern: from X to Y

    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower
    )

    if match:

        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(
            origin_text
        )

        arr_iata = resolve_location_to_iata(
            dest_text
        )

        return dep_iata, arr_iata

    # Pattern: to Y from X

    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower
    )

    if match:

        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(
            origin_text
        )

        arr_iata = resolve_location_to_iata(
            dest_text
        )

        return dep_iata, arr_iata

    # Pattern: destination trip from origin

    match = re.search(
        r"\b(.+?)\s+trip\s+from\s+(.+?)(?:[.!?]|$)",
        q_lower
    )

    if match:

        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(
            origin_text
        )

        arr_iata = resolve_location_to_iata(
            dest_text
        )

        return dep_iata, arr_iata

    # Pattern: X to Y

    match = re.search(
        r"\b(.+?)\s+to\s+(.+?)(?:[.!?]|$)",
        q_lower
    )

    if match:

        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(
            origin_text
        )

        arr_iata = resolve_location_to_iata(
            dest_text
        )

        if dep_iata or arr_iata:
            return dep_iata, arr_iata

    # Pattern: flights from X

    match = re.search(
        r"\bfrom\s+(.+?)(?:[.!?]|$)",
        q_lower
    )

    if match:

        origin_text = match.group(1)

        dep_iata = resolve_location_to_iata(
            origin_text
        )

        return dep_iata, None

    # Pattern: flights to X

    match = re.search(
        r"\bto\s+(.+?)(?:[.!?]|$)",
        q_lower
    )

    if match:

        dest_text = match.group(1)

        arr_iata = resolve_location_to_iata(
            dest_text
        )

        return None, arr_iata

    # Fallback: detect locations

    mentions = find_location_mentions(q)

    # Resolve locations in their original query order.
    # Prefer the first two distinct locations.

    resolved = []

    for mention in mentions:

        code = resolve_location_to_iata(mention)

        if code and code not in resolved:
            resolved.append(code)

    if len(resolved) >= 2:

        return resolved[0], resolved[1]

    if len(resolved) == 1:

        return DEFAULT_ORIGIN_IATA, resolved[0]

    return None, None


# ============================================================
# 12. FORMAT FLIGHT INFORMATION
# ============================================================

def format_flight(flight: dict):

    airline = (
        (flight.get("airline") or {}).get("name")
        or "Unknown airline"
    )

    flight_number = (
        (flight.get("flight") or {}).get("iata")
        or "Unknown flight number"
    )

    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure") or {}
    arr = flight.get("arrival") or {}

    # Departure details

    dep_airport = dep.get("airport") or "Unknown"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"

    dep_delay = dep.get("delay")

    dep_delay_text = (
        f"{dep_delay} minutes"
        if dep_delay is not None
        else "N/A"
    )

    # Arrival details

    arr_airport = arr.get("airport") or "Unknown"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"

    arr_delay = arr.get("delay")

    arr_delay_text = (
        f"{arr_delay} minutes"
        if arr_delay is not None
        else "N/A"
    )

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


# ============================================================
# 13. SEARCH FLIGHTS USING AVIATIONSTACK
# ============================================================

def search_flights(query: str, limit: int = 10):

    if not API_KEY:

        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    if limit < 1:
        return "Flight search limit must be at least 1."

    limit = min(limit, 100)

    # Extract route

    dep_iata, arr_iata = parse_route(query)

    # Build API parameters

    params = {
        "access_key": API_KEY,
        "limit": limit,
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    # API request

    try:

        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:

        return f"Flight API request failed: {e}"

    except ValueError:

        return "Flight API returned invalid JSON."

    # API error handling

    if "error" in data:

        error = data["error"] or {}

        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    # Extract flight data

    flight_data = data.get("data") or []

    if not flight_data:

        route_text = ""

        if dep_iata and arr_iata:

            route_text = (
                f" for route {dep_iata} to {arr_iata}"
            )

        elif dep_iata:

            route_text = f" from {dep_iata}"

        elif arr_iata:

            route_text = f" to {arr_iata}"

        return (
            f"No live flight data found{route_text}.\n\n"
            "Note: AviationStack provides flight status data, "
            "not ticket prices. For actual fare prices, "
            "use a flight-pricing API such as Amadeus."
        )

    # Route information

    route_info = "Global live flights"

    if dep_iata and arr_iata:

        route_info = (
            f"Live flights from {dep_iata} to {arr_iata}"
        )

    elif dep_iata:

        route_info = (
            f"Live flights from {dep_iata}"
        )

    elif arr_iata:

        route_info = (
            f"Live flights to {arr_iata}"
        )

    # Format results

    formatted_flights = [
        format_flight(flight)
        for flight in flight_data[:limit]
    ]

    return (
        f"{route_info}\n\n"
        + "\n\n---\n\n".join(formatted_flights)
    )


# ============================================================
# 14. TESTING
# ============================================================

if __name__ == "__main__":

    test_queries = [
        "Plan a 7 days Japan trip from Bangladesh",
        "Find flights from India to Japan",
        "Show flights to Dubai from Delhi",
        "Flights from Mumbai",
        "Flights to Singapore",
        "All country flight info",
        "DAC to NRT",
    ]

    for query in test_queries:

        print("\n" + "=" * 80)

        print("QUERY:", query)

        dep, arr = parse_route(query)

        print("DEPARTURE IATA:", dep)
        print("ARRIVAL IATA:", arr)

    print("\n" + "=" * 80)

    print(
        search_flights(
            "Plan a 7 days Japan trip from Bangladesh"
        )
    )
