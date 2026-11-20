from lobbycode.share import guns
import html, re
import time
width = 1024

colors = {
	"text": "#ffffff",
	"secondary_text": "#8b949e",
	"blue_text": "#58a6ff",
	"red_text": "#f85149",
	"icon_fill": "#ffffff",
	"border": "#3A86FF",
	"blue_accent": "#2a3a5f",
	"red_accent": "#3d1616",
	"accent_stop": "#11141b",
	"background": "#0d1117",
	"logo_color": "#3A86FF"
}

def sanitize_input(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    text = html.escape(text, quote=True)
    return text

def make_gun_symbols():
    final = ""
    for key, value in guns.items():
        final += f'''
			<symbol id="icon-{value["short"]}" viewBox="0 0 16 16">
				<g transform="scale(0.15094)">
					<path fill="#ffffff" d="{value["svg"]}" />
				</g>
			</symbol>
		'''
    return final

def get_player_svg(idx, gun, name, kills, deaths, kdr, time, fill, cap = 0, tak = 0):
	return f'''
		<g transform="translate(0, {idx*40})">
		<use xlink:href="#icon-{guns[gun]["short"]}" x="0" y="-12" width="16" height="16" />
		<text x="25" fill="{fill}">{sanitize_input(name)}</text>
		<text x="200" text-anchor="end" fill="white">{kills}</text>
		<text x="235" text-anchor="end" fill="white">{deaths}</text>
		<text x="290" text-anchor="end" fill="white">{kdr}</text>
		<text x="350" text-anchor="end" fill="#8b949e">{time}</text>
    <text x="385" text-anchor="end" fill="#8b949e">{cap}</text>
    <text x="385" fill="#8b949e">|{tak}</text>
		</g>
	'''

def make_team_svg(team_stats: list, fill: str):
	final = ""
	for i, data in enumerate(sorted(team_stats, key=lambda x: x["kills"], reverse=True)):
		final += get_player_svg(i, data["weapon"], data["player"], data["kills"], data["deaths"], data["kdr"], data["coopTime"], fill, data.get("cap", 0), data.get("tak", 0))
	return final

def final_svg(data: dict, game_no: int):
    blue_score, red_score = data["score"]["blue"], data["score"]["red"]
    blue_stats, red_stats = make_team_svg(data["stats"]["blue"], "#58a6ff"), make_team_svg(data["stats"]["red"], "#f85149")
    var_h = max(len(data["stats"]["blue"]), len(data["stats"]["red"]))*40
    map = data.get("map", "unkown").capitalize()
    server = data.get("server", "unkown").lower()
    time_diff = (int(time.time()* 1000) - data.get("score", {}).get("start", int(time.time() * 1000))) // 1000
    formatted_time = f"{time_diff//60}m {time_diff%60}s"
    return f'''
<svg width="1024" height="{230 + var_h}" viewBox="0 0 1024 {230 + var_h}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <defs>
    <style>
      .corner-border {{
        fill: none;
        stroke: #3A86FF;
        stroke-width: 3;
        stroke-linecap: round;
      }}
    </style>
    <linearGradient id="headerGradBlue" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#2a3a5f;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#11141b;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="headerGradRed" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3d1616;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#11141b;stop-opacity:1" />
    </linearGradient>
    {make_gun_symbols()}
  </defs>
  <rect width="1024" height="{230 + var_h}" rx="12" fill="#0d1117" stroke="#1c2533" stroke-width="1" />
  <g class="corner-border">
    <path d="M 25 100 V 25 H 100" />
    <path d="M 924 25 H 999 V 100" />
    <path d="M 25 {130 + var_h} V {130 + 75 + var_h} H 100" />
    <path d="M 924 {130 + 75 + var_h} H 999 V {130 + var_h}" />
  </g>
  <g font-family="Arial, Helvetica, sans-serif" font-weight="bold">
    <text x="50" y="90" font-size="16" fill="#8b949e"> Game <tspan fill="#ffffff">#{game_no}</tspan> | {server} | <tspan fill="#ffffff">{map}</tspan> — {formatted_time} </text>
    <text x="980" y="80" font-size="30" fill="#3A86FF" text-anchor="end">SHELL <tspan fill="#ffffff"> STRIKE</tspan>
    </text>
    <g transform="translate(45, 100)">
      <rect width="455" height="{85 + var_h}" rx="10" fill="#11141b" stroke="#1f2937" stroke-width="1" />
      <path d="M1,10 Q1,1 10,1 H445 Q454,1 454,10 V50 H1 Z" fill="url(#headerGradBlue)" />
      <text x="25" y="32" font-size="18" fill="#58a6ff">BLUE TEAM</text>
      <text x="430" y="32" font-size="22" fill="#ffffff" text-anchor="end">{blue_score}</text>
      <g transform="translate(25, 70)" font-size="11" fill="#8b949e">
        <text>PLAYER</text>
        <text x="200" text-anchor="end">K</text>
        <text x="235" text-anchor="end">D</text>
        <text x="290" text-anchor="end">KDR</text>
        <text x="350" text-anchor="end">TIME</text>
        <text x="385" text-anchor="end">CAP</text>
        <text x="410" text-anchor="end">|TAK</text>
      </g>
      <g transform="translate(25, 105)" font-size="15">
        {blue_stats}
      </g>
    </g>
    <g transform="translate(530, 100)">
      <rect width="455" height="{85 + var_h}" rx="10" fill="#11141b" stroke="#1f2937" stroke-width="1" />
      <path d="M1,10 Q1,1 10,1 H445 Q454,1 454,10 V50 H1 Z" fill="url(#headerGradRed)" />
      <text x="25" y="32" font-size="22" fill="#ffffff">{red_score}</text>
      <text x="430" y="32" font-size="18" fill="#f85149" text-anchor="end">RED TEAM</text>
      <g transform="translate(25, 70)" font-size="11" fill="#8b949e">
        <text>PLAYER</text>
        <text x="200" text-anchor="end">K</text>
        <text x="235" text-anchor="end">D</text>
        <text x="290" text-anchor="end">KDR</text>
        <text x="350" text-anchor="end">TIME</text>
        <text x="385" text-anchor="end">CAP</text>
        <text x="410" text-anchor="end">|TAK</text>
      </g>
      <g transform="translate(25, 105)" font-size="15">
        {red_stats}
      </g>
    </g>
  </g>
</svg>
'''.replace("\n", "")

sample_data = {
        "score": {
            "blue": 1,
            "red": 0,
            "names": [],
            "start": 1774842922186
        },
        "progress": {
            "capturing": 2,
            "captureProgress": 39,
            "numCapturing": 0,
            "capturePercent": 0.039,
            "stage": 6
        },
        "stats": {
            "blue": [],
            "red": [
                {
                    "player": "testtest",
                    "kills": 1,
                    "deaths": 1,
                    "kdr": 1,
                    "weapon": 3,
                    "unique": "qee2j5t9jh18re",
                    "coopTime": "0m 38s",
                    "cap": 1,
                    "tak": 1
                }
            ]
        },
         'map': 'cluckgrounds', 'server': 'uswest', 'code': 'slow-perm-wind', 'count': 10, 'config': {'locked': False, 'chat': False}
    }
# image_buffer = get_svg_to_png(final_svg(sample_data, 368))
# webhook_url = "https://discord.com/api/webhooks/1480160888945246269/hMCtpgi7vPCiDqLX9EsK2ydtDk70dGmQBrKf2aJBhTwd3Qh2yQE7h8LMekBIycJoqLFW"
# import requests
# files = {
#     "file": ("image.png", image_buffer, "image/png")
# }

# data = {
#     "content": "Image from buffer"
# }

# requests.post(webhook_url, data=data, files=files)
#print(final_svg(sample_data, 368))