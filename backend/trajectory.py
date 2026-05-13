import math

# ─────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────
R_EARTH    = 6_371_000   # mean Earth radius in meters
MU         = 3.986e14    # Earth gravitational parameter (m³/s²)
LAUNCH_LAT = 28.392      # Cape Canaveral latitude  (degrees)
LAUNCH_LON = -80.603     # Cape Canaveral longitude (degrees)


def simulate_launch(duration=600, steps=600):
    """
    Simulates a rocket gravity-turn ascent from Cape Canaveral to ~400km LEO.
    Returns a list of dicts, one per timestep:
      { t, lat, lon, alt_m, vel_ms }
    """

    points = []

    for i in range(steps + 1):

        # ── 1. TIME ──────────────────────────────────────────────────────
        # Evenly space timesteps from 0 to `duration` seconds.
        t = (i / steps) * duration


        # ── 2. ALTITUDE PROFILE ──────────────────────────────────────────
        # A real rocket flies in three phases. We model each separately.

        if t < 10:
            # PHASE A: Vertical rise (0–10 seconds)
            # Rocket goes straight up to clear the launch tower.
            # Simple quadratic: alt grows as t².
            # At t=10 → alt ≈ 500m. Feels right.
            alt_m = 5 * t ** 2

        elif t < 150:
            # PHASE B: Gravity turn (10–150 seconds, through Max-Q)
            # The rocket pitches over and follows a curved arc.
            # We blend two terms:
            #   - a quadratic climb (still accelerating upward)
            #   - the pitch-over starts eating into vertical velocity
            # tr = normalized time within this phase (0 → 1)
            tr = (t - 10) / 140
            alt_m = 500 + (tr ** 1.6) * 95_000

        else:
            # PHASE C: Upper stage burn to orbit (150–600 seconds)
            # Second stage ignites after MECO and stage separation.
            # Linear climb from ~95km toward 400km.
            # tr = normalized time within this phase (0 → 1)
            tr = (t - 150) / 450
            alt_m = 95_000 + tr * 305_000


        # ── 3. VELOCITY PROFILE ──────────────────────────────────────────
        # Orbital velocity at 400km = sqrt(MU / (R + alt)) ≈ 7,670 m/s
        # We ramp velocity from 0 → ~7,800 m/s over the flight.

        if t < 10:
            # Slow vertical rise, only ~40 m/s at liftoff
            vel_ms = t * 40

        elif t < 155:
            # First stage: aggressive acceleration
            # Goes from ~400 m/s at t=10 to ~3,500 m/s at MECO
            tr = (t - 10) / 145
            vel_ms = 400 + tr * 3_100

        else:
            # Second stage: continues to orbital velocity
            tr = (t - 155) / 445
            vel_ms = 3_500 + tr * 4_300


        # ── 4. DOWNRANGE DISTANCE ────────────────────────────────────────
        # How far along the ground track has the rocket traveled?
        # We integrate a rough horizontal speed over time.
        # Early on most velocity is vertical; later it's mostly horizontal.
        # We model the fraction that's horizontal using a pitch angle proxy.

        if t < 10:
            # Nearly vertical — almost no downrange movement
            downrange_m = 0.0

        elif t < 150:
            # Pitching over — horizontal fraction grows from 0 → 1
            # pitch_fraction ramps from 0 (vertical) to 1 (horizontal)
            # using a smooth curve so the turn feels natural
            tr = (t - 10) / 140
            pitch_fraction = tr ** 2.0

            # Approximate horizontal speed at this moment
            # (We re-derive velocity inline here for the integral)
            v_now = 400 + tr * 3_100
            h_speed = v_now * pitch_fraction

            # Accumulate: downrange ≈ average horizontal speed × elapsed time
            # This is a simplified integral — good enough for visualization
            downrange_m = 0.5 * h_speed * (t - 10)

        else:
            # Upper stage: mostly horizontal, velocity is nearly all downrange
            tr_prev = 1.0   # at end of phase B
            v_at_meco = 3_500
            downrange_at_meco = 0.5 * v_at_meco * 140

            tr = (t - 150) / 450
            v_now = 3_500 + tr * 4_300
            extra_downrange = 0.5 * (v_at_meco + v_now) * (t - 150)
            downrange_m = downrange_at_meco + extra_downrange


        # ── 5. LAT / LON FROM DOWNRANGE ──────────────────────────────────
        # We need to convert a downrange distance along the surface into
        # actual lat/lon coordinates.
        #
        # We use the spherical law of cosines (haversine forward formula).
        # The rocket launches northeast from Cape Canaveral on a heading
        # of ~44° to achieve a 28.5° orbital inclination.
        #
        # Inputs:
        #   lat0, lon0  = launch site in radians
        #   bearing     = direction of travel in radians
        #   ang_dist    = downrange_m / R_EARTH (central angle in radians)

        lat0_r = math.radians(LAUNCH_LAT)
        lon0_r = math.radians(LAUNCH_LON)
        bearing = math.radians(44.0)          # NE heading for 28.5° inc
        ang_dist = downrange_m / R_EARTH      # central angle (radians)

        # Spherical forward formula:
        lat_r = math.asin(
            math.sin(lat0_r) * math.cos(ang_dist) +
            math.cos(lat0_r) * math.sin(ang_dist) * math.cos(bearing)
        )

        lon_r = lon0_r + math.atan2(
            math.sin(bearing) * math.sin(ang_dist) * math.cos(lat0_r),
            math.cos(ang_dist) - math.sin(lat0_r) * math.sin(lat_r)
        )

        # Convert back to degrees
        lat = math.degrees(lat_r)
        lon = math.degrees(lon_r)


        # ── 6. STORE THE POINT ───────────────────────────────────────────
        points.append({
            "t":      round(t, 2),
            "lat":    round(lat, 6),
            "lon":    round(lon, 6),
            "alt_m":  round(alt_m, 1),
            "vel_ms": round(vel_ms, 1),
        })

    return points


# ─────────────────────────────────────────
# QUICK SANITY CHECK — run directly
# ─────────────────────────────────────────
if __name__ == "__main__":
    pts = simulate_launch()

    print(f"Total points: {len(pts)}\n")
    print(f"{'t':>6}  {'alt_m':>10}  {'vel_ms':>8}  {'lat':>8}  {'lon':>9}")
    print("-" * 52)

    # Print every 60th point (every ~60 seconds of flight)
    for p in pts[::60]:
        print(f"{p['t']:>6.0f}  {p['alt_m']:>10.0f}  {p['vel_ms']:>8.0f}  {p['lat']:>8.3f}  {p['lon']:>9.3f}")

    print("\nSanity checks:")
    last = pts[-1]
    print(f"  Final altitude : {last['alt_m']/1000:.1f} km  (target ~400 km)")
    print(f"  Final velocity : {last['vel_ms']:.0f} m/s  (orbital ~7,670 m/s)")
    print(f"  Final lat/lon  : {last['lat']:.2f}°N, {last['lon']:.2f}°")