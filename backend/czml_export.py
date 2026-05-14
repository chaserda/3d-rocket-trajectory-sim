import json
import math

# ─────────────────────────────────────────────────────────────────────────────
# PART 1: COORDINATE CONVERSION
# Converting lat/lon/altitude → Cartesian3 (ECEF)
# ─────────────────────────────────────────────────────────────────────────────
#
# Earth is not a perfect sphere — it bulges at the equator slightly.
# The WGS84 ellipsoid is the mathematical model of Earth's shape that
# GPS, maps, and Cesium all use. It has two radius values:
#
#   a  = equatorial radius (bigger — Earth is wider at the equator)
#   b  = polar radius     (smaller — Earth is flatter at the poles)
#
# The difference is small (~21km) but matters for accurate coordinates.

WGS84_A  = 6_378_137.0        # equatorial radius in meters
WGS84_E2 = 0.00669437999014   # eccentricity squared (describes the "squashedness")


def lat_lon_alt_to_cartesian(lat_deg, lon_deg, alt_m):
    """
    Converts a geographic position (latitude, longitude, altitude)
    into ECEF Cartesian3 coordinates (x, y, z) in meters.

    ECEF = Earth-Centered, Earth-Fixed
    The origin (0, 0, 0) is the center of the Earth.
    The axes are:
      X → points out through the equator at 0°N, 0°E
      Y → points out through the equator at 0°N, 90°E
      Z → points out through the North Pole

    Why does Cesium need this instead of lat/lon/alt?
    Because Cesium does 3D math (matrix transforms, interpolation)
    in a flat Cartesian space. Lat/lon is a curved coordinate system
    and interpolating between two lat/lon points produces a curved
    path that can go through the Earth. Cartesian3 interpolation
    stays on the surface.
    """

    # Convert degrees to radians — all Python trig functions use radians
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    # N = the radius of curvature at this latitude
    # At the equator (lat=0), N = a (full equatorial radius)
    # At the poles (lat=90°), N is smaller because Earth is flatter there
    # This formula accounts for Earth's ellipsoidal shape
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(lat) ** 2)

    # Now compute x, y, z
    # Think of it as:
    #   Start at Earth's center
    #   Move out to the surface along the equatorial plane (x, y)
    #   Move up to your latitude (z)
    #   Then add altitude on top of that
    x = (N + alt_m) * math.cos(lat) * math.cos(lon)
    y = (N + alt_m) * math.cos(lat) * math.sin(lon)
    z = (N * (1 - WGS84_E2) + alt_m) * math.sin(lat)
    # Note: the z formula uses (1 - e²) to account for Earth's polar flattening

    return x, y, z


# ─────────────────────────────────────────────────────────────────────────────
# PART 2: BUILD THE CZML DOCUMENT PACKET
# ─────────────────────────────────────────────────────────────────────────────
#
# The document packet is always the first item in a CZML file.
# It sets up the scene name and most importantly the clock —
# what time range does this simulation cover and how fast does it play.

def build_document_packet(start_iso, end_iso, multiplier=8):
    """
    Builds the CZML document packet (the scene settings).

    start_iso / end_iso: ISO 8601 timestamps like "2025-03-15T14:00:00Z"
    multiplier: playback speed. 8 = plays 8x faster than real time.
    """
    return {
        "id": "document",         # must be exactly this string
        "name": "APEX-1 Mission", # human readable, shows in Cesium UI
        "version": "1.0",         # CZML spec version, always 1.0
        "clock": {
            # interval = the full time range of the simulation
            # format is "start/end" separated by a slash
            "interval": f"{start_iso}/{end_iso}",

            # where the clock starts when you open the file
            "currentTime": start_iso,

            # 8x faster than real time — full 10min flight in ~75 seconds
            "multiplier": multiplier,

            # LOOP_STOP = play once and stop at the end
            # alternatives: UNBOUNDED (keep going), LOOP_STOP (stop), CLAMPED
            "range": "LOOP_STOP",

            # SYSTEM_CLOCK_MULTIPLIER = advance clock based on real time × multiplier
            "step": "SYSTEM_CLOCK_MULTIPLIER"
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# PART 3: BUILD THE POSITION ARRAY
# ─────────────────────────────────────────────────────────────────────────────
#
# This is the core of the file — the list of positions over time.
# Format: [t, x, y, z,  t, x, y, z,  t, x, y, z, ...]
# where t = seconds since epoch, x/y/z = Cartesian3 in meters

def build_position_array(points):
    """
    Takes your list of trajectory dicts and returns a flat list
    in the CZML cartesian format: [t, x, y, z, t, x, y, z, ...]

    Each group of 4 numbers is one timestep.
    """
    cartesian = []

    for p in points:
        # Convert this point's lat/lon/alt to x/y/z
        x, y, z = lat_lon_alt_to_cartesian(p["lat"], p["lon"], p["alt_m"])

        # Append as a group of 4: time offset, then x, y, z
        # Round x/y/z to 2 decimal places — centimeter precision is plenty
        cartesian.append(round(p["t"], 2))
        cartesian.append(round(x, 2))
        cartesian.append(round(y, 2))
        cartesian.append(round(z, 2))

    return cartesian


# ─────────────────────────────────────────────────────────────────────────────
# PART 4: BUILD THE ROCKET ENTITY PACKET
# ─────────────────────────────────────────────────────────────────────────────
#
# This packet describes the rocket itself:
#   - its position over time (the cartesian array from above)
#   - what it looks like (a glowing point)
#   - its trail (the path line behind it)
#   - its label (the name tag)

def build_rocket_packet(points, start_iso, end_iso):
    """
    Builds the CZML entity packet for the rocket.
    """

    # First get the full time range string — used in the availability field
    availability = f"{start_iso}/{end_iso}"

    # Build the position array from all your trajectory points
    cartesian_array = build_position_array(points)

    return {
        # Unique ID — you'll use this in JavaScript:
        # ds.entities.getById("rocket")
        "id": "rocket",

        # Human readable name — shows in Cesium's info box
        "name": "APEX-1 LV-9",

        # availability = what time range this entity exists
        # Before or after this range, the entity is invisible
        "availability": availability,

        # ── POSITION ─────────────────────────────────────────────────────
        "position": {
            # LAGRANGE interpolation smoothly curves between your data points
            # Cesium renders at 60fps but you only have 1 point per second
            # LAGRANGE fills in the gaps with a smooth curve
            "interpolationAlgorithm": "LAGRANGE",

            # How many neighboring points to use when interpolating
            # 5 = look at 5 surrounding points to draw each curve segment
            # Higher = smoother but more processing
            "interpolationDegree": 5,

            # INERTIAL = coordinates fixed in space (not rotating with Earth)
            # Use INERTIAL for anything flying through the air or space
            # Use FIXED for things attached to the ground
            "referenceFrame": "INERTIAL",

            # epoch = the timestamp that t=0 refers to
            # All your time values in cartesian are seconds since this moment
            "epoch": start_iso,

            # The actual position data: [t, x, y, z, t, x, y, z, ...]
            "cartesian": cartesian_array
        },

        # ── POINT ────────────────────────────────────────────────────────
        # This is the glowing dot that represents the rocket on screen
        "point": {
            # Size in pixels on screen
            "pixelSize": 10,

            # Main color: cyan blue, fully opaque
            # RGBA values 0-255. Last value (255) = fully visible.
            "color": {
                "rgba": [0, 180, 255, 255]
            },

            # Outline adds a white ring around the dot
            # Makes it stand out against the dark globe
            "outlineColor": {
                "rgba": [255, 255, 255, 160]
            },
            "outlineWidth": 1,

            # scaleByDistance: make the dot slightly smaller when zoomed out
            # Format: [near_distance, near_scale, far_distance, far_scale]
            # At 100km away: 1.5x size. At 50,000km away: 0.8x size.
            "scaleByDistance": {
                "nearFarScalar": [100000, 1.5, 50000000, 0.8]
            }
        },

        # ── PATH ─────────────────────────────────────────────────────────
        # This draws the trail line behind (and optionally ahead of) the rocket
        "path": {
            # material = what the line looks like
            # polylineGlow makes it glow like a neon light
            "material": {
                "polylineGlow": {
                    # Base color of the glow — same cyan as the dot
                    "color": {
                        "rgba": [0, 180, 255, 255]
                    },
                    # How strong the glow effect is (0-1)
                    # 0.2 = subtle glow, not overwhelming
                    "glowPower": 0.2,
                    # taperPower: how much the line fades toward its ends
                    # 1.0 = no taper (uniform thickness)
                    "taperPower": 1.0
                }
            },

            # Line thickness in pixels
            "width": 2,

            # leadTime: seconds AHEAD of current time to draw the path
            # 0 = don't show the future path
            # Set to a large number to show the full planned trajectory
            "leadTime": 0,

            # trailTime: seconds BEHIND current time to keep drawing
            # 99999 = keep the entire history visible
            # Set to 60 if you only want the last 60 seconds of trail
            "trailTime": 99999,

            # How precisely Cesium samples the path for drawing
            # Lower number = smoother line, more processing
            "resolution": 5
        },

        # ── LABEL ────────────────────────────────────────────────────────
        # The text name tag that floats next to the rocket
        "label": {
            "text": "APEX-1",
            "font": "12px monospace",

            # FILL = solid text (no outline on the letters themselves)
            "style": "FILL_AND_OUTLINE",

            # Text color
            "fillColor": {
                "rgba": [0, 180, 255, 220]
            },

            # Dark outline behind the text so it's readable on any background
            "outlineColor": {
                "rgba": [0, 0, 0, 200]
            },
            "outlineWidth": 2,

            # Offset the label so it doesn't sit on top of the dot
            # [x, y] in pixels. 14 right, -4 up.
            "pixelOffset": {
                "cartesian2": [14, -4]
            },

            # distanceDisplayCondition: hide the label when too far away
            # Only show when camera is between 0m and 80,000,000m away
            # Prevents the label from cluttering a zoomed-out view
            "distanceDisplayCondition": {
                "nearFarScalar": [0, 80000000]
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# PART 5: BUILD THE LAUNCH PAD MARKER
# ─────────────────────────────────────────────────────────────────────────────
#
# A separate static entity for the launch site.
# This doesn't move — it just sits on the ground at Cape Canaveral.

def build_launch_pad_packet():
    """
    Builds a CZML entity for the launch pad marker.
    A static red dot on the ground at Cape Canaveral.
    """

    # Convert Cape Canaveral to Cartesian3 at ground level (alt=0)
    x, y, z = lat_lon_alt_to_cartesian(28.392, -80.603, 0)

    return {
        "id": "launch_pad",
        "name": "LC-39A · Cape Canaveral",

        # position is a single fixed point — not an array over time
        # because this object doesn't move
        "position": {
            "cartesian": [x, y, z]
        },

        "point": {
            "pixelSize": 10,
            "color": {
                "rgba": [255, 80, 80, 255]   # red
            },
            "outlineColor": {
                "rgba": [255, 255, 255, 200]
            },
            "outlineWidth": 1,
            # clampToGround would be ideal here but requires terrain
            # so we just set it at altitude 0
            "heightReference": "NONE"
        },

        "label": {
            "text": "LC-39A",
            "font": "11px monospace",
            "style": "FILL_AND_OUTLINE",
            "fillColor": {"rgba": [255, 80, 80, 220]},
            "outlineColor": {"rgba": [0, 0, 0, 200]},
            "outlineWidth": 2,
            "pixelOffset": {"cartesian2": [12, 0]},
            "distanceDisplayCondition": {"nearFarScalar": [0, 10000000]}
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# PART 6: THE MAIN EXPORT FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def export_czml(points, filename):
    """
    Takes your trajectory points and writes a complete CZML file.

    points   — list of dicts from simulate_launch()
               each dict has: t, lat, lon, alt_m, vel_ms
    filename — where to write the file, e.g. "frontend/apex1.czml"
    """

    # ── Work out the time range ───────────────────────────────────────────
    # We use a fixed launch date/time as the epoch
    # The Z at the end means UTC timezone
    START_ISO = "2025-03-15T14:00:00Z"

    # End time = start + however many seconds your simulation covers
    # Your simulation is 600 seconds = 10 minutes
    total_seconds = int(points[-1]["t"])  # last point's t value

    # Build end timestamp by adding total_seconds to the start
    # Simple string math since we know the format
    # 14:00:00 + 600 seconds = 14:10:00
    start_minutes = 0
    end_seconds_total = 14 * 3600 + total_seconds
    end_h = end_seconds_total // 3600
    end_m = (end_seconds_total % 3600) // 60
    end_s = end_seconds_total % 60
    END_ISO = f"2025-03-15T{end_h:02d}:{end_m:02d}:{end_s:02d}Z"

    # ── Assemble the CZML array ───────────────────────────────────────────
    # A CZML file is just a Python list that gets written as JSON
    # Order matters: document packet must be first
    czml = [
        build_document_packet(START_ISO, END_ISO, multiplier=8),
        build_rocket_packet(points, START_ISO, END_ISO),
        build_launch_pad_packet()
    ]

    # ── Write to file ─────────────────────────────────────────────────────
    # json.dumps converts the Python list to a JSON string
    # indent=2 makes it human-readable (each field on its own line)
    with open(filename, "w") as f:
        json.dump(czml, f, indent=2)

    # ── Print a summary ───────────────────────────────────────────────────
    total_points = len(points)
    file_size_kb = len(json.dumps(czml)) / 1024

    print(f"CZML file written: {filename}")
    print(f"  Time range  : {START_ISO} → {END_ISO}")
    print(f"  Data points : {total_points} positions")
    print(f"  Packets     : 3 (document, rocket, launch pad)")
    print(f"  File size   : {file_size_kb:.1f} KB")
    print(f"\nFirst position in cartesian:")
    x, y, z = lat_lon_alt_to_cartesian(
        points[0]["lat"], points[0]["lon"], points[0]["alt_m"]
    )
    print(f"  t=0 → x={x:.0f}, y={y:.0f}, z={z:.0f}")
    print(f"\nLast position in cartesian:")
    x, y, z = lat_lon_alt_to_cartesian(
        points[-1]["lat"], points[-1]["lon"], points[-1]["alt_m"]
    )
    print(f"  t={points[-1]['t']:.0f} → x={x:.0f}, y={y:.0f}, z={z:.0f}")


# ─────────────────────────────────────────────────────────────────────────────
# PART 7: RUN IT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Import your trajectory simulation
    from trajectory import simulate_launch

    print("Running trajectory simulation...")
    points = simulate_launch()
    print(f"Generated {len(points)} trajectory points\n")

    print("Exporting to CZML...")
    export_czml(points, "frontend/apex1.czml")

    print("\nDone. Open frontend/apex1.czml in a text editor")
    print("to verify it looks like valid JSON before loading into Cesium.")