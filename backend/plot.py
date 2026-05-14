import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import math

from trajectory import simulate_launch
pts = simulate_launch()

t = [p["t"] for p in pts] # list of times
alt_km = [p["alt_m"] / 1000 for p in pts] # altitudes in km
vel_kms = [p["vel_ms"] for p in pts] # velocities in km/s
lats = [p["lat"] for p in pts] # latitudes in degrees
lons = [p["lon"] for p in pts] # longitudes in degrees

downrange_km = [] # list to hold downrange distances in km
for p in pts:
    lat0 = math.radians(28.392) # launch site latitude in radians
    lon0 = math.radians(-80.603) # launch site longitude in radians
    lat1 = math.radians(p["lat"]) # current point lat in radians
    lon1 = math.radians(p["lon"])  # current point lon in radians
    dlat = lat1 - lat0 # difference in latitude
    dlon = lon1 - lon0 # difference in longitude
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat0) * math.cos(lat1) * math.sin(dlon / 2) ** 2) # haversine formula
    km = 6371 * 2 * math.asin(math.sqrt(a))  # convert to km
    downrange_km.append(km) # downrange distance in km

# SETUP THE FIGURE AND SUBPLOTS
fig = plt.figure(figsize=(14, 9), facecolor="#0a0f1a")
fig.suptitle("APEX-1 — Trajectory Verification",
             color="white", fontsize=14, fontweight="bold", y=0.98)
gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

# STYLE THE FIGURE AND AXES
def style_ax(ax, title, xlabel, ylabel):
    ax.set_facecolor("#0d1520")
    ax.set_title(title, color="#a0c8e0", fontsize=10, pad=8)
    ax.set_xlabel(xlabel, color="#4a7090", fontsize=9)
    ax.set_ylabel(ylabel, color="#4a7090", fontsize=9)
    ax.tick_params(colors="#4a7090", labelsize=8)
    ax.grid(color="#1a3040", linewidth=0.6, linestyle="--")
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a3040")

# CHART 1: ALTITUDE vs TIME
# Top-left slot in the 2x2 grid
# X axis = time in seconds, Y axis = altitude in km
ax1 = fig.add_subplot(gs[0, 0])
ax1.plot(t, alt_km, color="#00b4ff", linewidth=1.8)

# These horizontal dashed lines are reference markers
ax1.axhline(100, color="#ffd04d", linewidth=0.8,
            linestyle="--", label="Kármán line (100km)")
ax1.axhline(400, color="#00ffaa", linewidth=0.8,
            linestyle="--", label="Target orbit (400km)")
ax1.legend(fontsize=7, facecolor="#0d1520", labelcolor="white", framealpha=0.8)
style_ax(ax1, "Altitude vs Time", "Time (s)", "Altitude (km)")

# CHART 2: VELOCITY vs TIME
# Top-right slot in the 2x2 grid
# X axis = time in seconds, Y axis = velocity in km/s
ax2 = fig.add_subplot(gs[0, 1])
ax2.plot(t, vel_kms, color="#00ffaa", linewidth=1.8)
ax2.axhline(7670, color="#ffd04d", linewidth=0.8,
            linestyle="--", label="Orbital velocity ~7.67 m/s")
ax2.legend(fontsize=7, facecolor="#0d1520",
           labelcolor="white", framealpha=0.8)
style_ax(ax2, "Velocity vs Time", "Time (s)", "Velocity (km/s)")

# CHART 3: GROUND TRACK (LATITUDE vs LONGITUDE)
# Bottom-left slot in the 2x2 grid
ax3 = fig.add_subplot(gs[1, 0])
ax3.plot(lons, lats, color="#b48dff", linewidth=1.8)
ax3.plot(lons[0], lats[0], "o", color="#ff5252",
         markersize=7, label="Launch (Cape Canaveral)", zorder=5)
ax3.plot(lons[-1], lats[-1], "o", color="#00ffaa",
         markersize=7, label="SECO / orbit insertion", zorder=5)

# Mark key events on the ground track
milestones = [74, 150, 153]
labels     = ["Max-Q", "MECO", "Stage Sep"]
for mi, lbl in zip(milestones, labels):
    idx = min(mi, len(pts)-1)
    ax3.plot(pts[idx]["lon"], pts[idx]["lat"],
             "^", color="#ffd04d", markersize=5, zorder=5)
    ax3.annotate(lbl,
                 (pts[idx]["lon"], pts[idx]["lat"]),
                 textcoords="offset points", xytext=(6, 4),
                 color="#ffd04d", fontsize=7)

ax3.legend(fontsize=7, facecolor="#0d1520",
           labelcolor="white", framealpha=0.8)
style_ax(ax3, "Ground Track", "Longitude (°)", "Latitude (°)")

# CHART 4: ALTITUDE vs DOWNRANGE
# Bottom-right slot in the 2x2 grid
downrange_km = []
for p in pts:
    import math
    lat0 = math.radians(28.392)
    lon0 = math.radians(-80.603)
    lat1 = math.radians(p["lat"])
    lon1 = math.radians(p["lon"])
    dlat = lat1 - lat0
    dlon = lon1 - lon0
    a = (math.sin(dlat/2)**2 +
         math.cos(lat0) * math.cos(lat1) * math.sin(dlon/2)**2)
    downrange_km.append(6371 * 2 * math.asin(math.sqrt(a)))

ax4 = fig.add_subplot(gs[1, 1])
ax4.plot(downrange_km, alt_km, color="#ff9d4d", linewidth=1.8)
ax4.axhline(100, color="#ffd04d", linewidth=0.8,
            linestyle="--", label="Kármán line")
ax4.legend(fontsize=7, facecolor="#0d1520",
           labelcolor="white", framealpha=0.8)
style_ax(ax4, "Altitude vs Downrange", "Downrange (km)", "Altitude (km)")


# SAVE AND SHOW THE FIGURE
plt.savefig("backend/trajectory_check.png",
            dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.show()
print("Saved to backend/trajectory_check.png")