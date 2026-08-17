"""Persistent Tony Stark-inspired HUD for Jarvis."""

from __future__ import annotations

import argparse
import json
import os
import platform
import queue
import shutil
import socket
import sqlite3
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT_FILE = Path(os.getenv("JARVIS_SPLASH_PORT_FILE", "/tmp/jarvis_splash_port.txt"))
STATE_FILE = Path(os.getenv("JARVIS_SPLASH_STATE_FILE", "/tmp/jarvis_splash_state.json"))

HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>JARVIS // Tactical Interface</title>
  <style>
    :root {
      color-scheme: dark;
      --cyan: #77f5ff;
      --cyan-soft: rgba(119,245,255,.55);
      --blue: #238dff;
      --violet: #b277ff;
      --amber: #ffd36b;
      --green: #43ffd0;
      --ink: #02070e;
      --panel: rgba(5, 21, 35, .72);
      --line: rgba(119,245,255,.22);
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: var(--ink); }
    body {
      display: grid; place-items: center; color: #dffaff;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 50% 48%, rgba(13,77,117,.24), transparent 26%),
        radial-gradient(circle at 50% 50%, #061526 0%, #02070e 62%, #010308 100%);
      transition: background .7s ease;
    }
    body::before {
      content: ""; position: fixed; inset: 0; pointer-events: none; opacity: .35;
      background-image: linear-gradient(rgba(119,245,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(119,245,255,.035) 1px, transparent 1px);
      background-size: 42px 42px; mask-image: radial-gradient(circle, black 15%, transparent 75%);
    }
    .hud { position: relative; width: min(96vw, 1180px); height: min(94vh, 820px); min-height: 560px; }
    .orbital-stage { position: absolute; left: 50%; top: 50%; width: min(73vmin, 650px); aspect-ratio: 1; transform: translate(-50%, -50%); }
    .halo, .ring, .arc, .ticks, .scan, .orbit, .core { position: absolute; border-radius: 50%; }
    .halo { inset: 4%; background: radial-gradient(circle, rgba(84,223,255,.17), rgba(3,17,29,.25) 42%, transparent 70%); filter: blur(14px); animation: breathe 4s ease-in-out infinite; }
    .ring { inset: 11%; border: 1px solid var(--line); box-shadow: 0 0 40px rgba(35,141,255,.12), inset 0 0 30px rgba(119,245,255,.06); }
    .ring.one { animation: rotate 18s linear infinite; }
    .ring.two { inset: 18%; border-color: rgba(35,141,255,.48); border-style: dashed; animation: rotate-reverse 28s linear infinite; }
    .ring.three { inset: 28%; border: 1px solid rgba(119,245,255,.45); animation: rotate 14s linear infinite; }
    .ring.four { inset: 37%; border-color: rgba(119,245,255,.16); animation: breathe 3.2s ease-in-out infinite; }
    .arc { inset: 6%; border: 3px solid transparent; border-top-color: var(--cyan); border-left-color: rgba(119,245,255,.35); transform: rotate(-28deg); filter: drop-shadow(0 0 8px var(--cyan)); animation: rotate 9s linear infinite; }
    .arc.two { inset: 23%; border-width: 2px; border-right-color: var(--blue); border-bottom-color: rgba(35,141,255,.2); transform: rotate(140deg); animation-duration: 6s; animation-direction: reverse; }
    .ticks { inset: 2%; background: repeating-conic-gradient(from 0deg, rgba(119,245,255,.7) 0 1deg, transparent 1deg 9deg); mask: radial-gradient(circle, transparent 0 72%, black 72.5% 73.2%, transparent 73.6%); opacity: .65; animation: rotate-reverse 34s linear infinite; }
    .scan { inset: 7%; background: conic-gradient(from 0deg, transparent 0 72%, rgba(119,245,255,.28) 77%, transparent 83% 100%); mix-blend-mode: screen; filter: blur(1px); animation: rotate 3.6s linear infinite; }
    .orbit { inset: 14%; animation: rotate 12s linear infinite; }
    .orbit::before, .orbit::after { content: ""; position: absolute; width: 8px; height: 8px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 14px 4px var(--cyan-soft); }
    .orbit::before { top: -4px; left: 50%; } .orbit::after { bottom: 14%; right: -4px; background: var(--blue); box-shadow: 0 0 14px 4px rgba(35,141,255,.45); }
    .core { inset: 30%; border-radius: 50%; display: grid; place-items: center; background: radial-gradient(circle at center, rgba(6,22,37,.45) 0%, rgba(2,9,19,.92) 56%, rgba(2,9,19,1) 100%); box-shadow: inset 0 0 60px rgba(79,232,255,.18), 0 0 70px rgba(26,168,255,.15); overflow: hidden; }
    .core::before { content: ""; position: absolute; inset: 7%; border-radius: 50%; border: 1px solid rgba(79,232,255,.35); animation: pulse 2.8s ease-in-out infinite; }
    .reactor { position: relative; width: 54%; aspect-ratio: 1; border-radius: 50%; border: 2px solid var(--cyan); box-shadow: 0 0 12px var(--cyan), 0 0 35px rgba(119,245,255,.55), inset 0 0 22px rgba(119,245,255,.55); animation: reactor-pulse 2.4s ease-in-out infinite; }
    .reactor::before { content: ""; position: absolute; inset: 19%; border-radius: 50%; border: 1px solid rgba(255,255,255,.8); }
    .reactor::after { content: ""; position: absolute; inset: 39%; border-radius: 50%; background: #e8ffff; box-shadow: 0 0 22px 8px var(--cyan); border: 0; }
    .center-brand { display: none; }
    .corner { position: absolute; width: 26px; height: 26px; border-color: rgba(119,245,255,.55); opacity: .7; }
    .corner.tl { left: 0; top: 0; border-left: 1px solid; border-top: 1px solid; } .corner.tr { right: 0; top: 0; border-right: 1px solid; border-top: 1px solid; }
    .corner.bl { left: 0; bottom: 0; border-left: 1px solid; border-bottom: 1px solid; } .corner.br { right: 0; bottom: 0; border-right: 1px solid; border-bottom: 1px solid; }
    .panel { position: absolute; width: 220px; padding: 16px 17px; border: 1px solid var(--line); background: linear-gradient(135deg, rgba(9,34,51,.78), rgba(2,10,18,.42)); box-shadow: 0 12px 40px rgba(0,0,0,.24), inset 0 0 30px rgba(119,245,255,.035); backdrop-filter: blur(12px); }
    .panel::before { content: ""; position: absolute; left: 0; top: 0; width: 34px; height: 2px; background: var(--cyan); box-shadow: 0 0 14px var(--cyan); }
    .panel.left { left: 3%; top: 22%; } .panel.right { right: 3%; top: 31%; }
    .eyebrow { color: #7eb7c3; font-size: 10px; letter-spacing: .22em; text-transform: uppercase; }
    .metric { margin-top: 9px; display: flex; align-items: baseline; justify-content: space-between; gap: 12px; font-size: 13px; color: #a8d8df; }
    .metric strong { color: #ebffff; font-size: 15px; font-weight: 650; }
    .meter { height: 3px; margin-top: 8px; overflow: hidden; background: rgba(119,245,255,.1); }
    .meter i { display: block; width: 72%; height: 100%; background: linear-gradient(90deg, var(--blue), var(--cyan)); box-shadow: 0 0 10px var(--cyan); animation: meter 4s ease-in-out infinite alternate; }
    .audio-meter { margin-top: 10px; }
    .audio-meter i { animation: none; width: 0%; transition: width .08s ease-out; background: linear-gradient(90deg, var(--blue), var(--cyan), #f3ffff); }
    .suit-overlay { --suit-blue: #42d9ff; --suit-blue-soft: rgba(66,217,255,.48); --suit-red: #8e1c2a; --suit-red-deep: #380912; --suit-gold: #d9aa55; --suit-gold-bright: #ffe8a3; position: absolute; inset: 0; z-index: 20; display: none; place-items: center; pointer-events: none; background: radial-gradient(circle at 50% 50%, rgba(4,49,79,.42), rgba(1,6,13,.76) 42%, rgba(1,5,10,.34) 76%, transparent 100%); opacity: 0; }
    .suit-overlay.active { display: grid; animation: overlay-in .7s ease-out forwards; }
    .suit-overlay::before { content: ""; position: absolute; inset: 9%; border: 1px solid rgba(119,245,255,.18); clip-path: polygon(0 0, 18% 0, 18% 1px, 0 1px, 0 16%, 1px 16%, 1px 0, 100% 0, 100% 16%, calc(100% - 1px) 16%, calc(100% - 1px) 0, 82% 0, 82% 1px, 100% 1px, 100% 100%, 82% 100%, 82% calc(100% - 1px), 100% calc(100% - 1px), 100% 84%, calc(100% - 1px) 84%, calc(100% - 1px) 100%, 0 100%, 0 84%, 1px 84%, 1px 100%, 18% 100%, 18% calc(100% - 1px), 0 calc(100% - 1px)); }
    .assembly-label { position: absolute; top: 12%; color: var(--suit-blue); font-size: 11px; letter-spacing: .3em; text-shadow: 0 0 14px var(--suit-blue); }
    .assembly-label::before { content: "◈"; margin-right: 10px; }
    .assembly-stage { position: relative; width: min(42vmin, 360px); height: min(66vmin, 520px); filter: drop-shadow(0 0 22px rgba(66,217,255,.28)); }
    .assembly-stage::before { content: ""; position: absolute; inset: 0; opacity: .38; background: linear-gradient(rgba(66,217,255,.16) 1px, transparent 1px), linear-gradient(90deg, rgba(66,217,255,.16) 1px, transparent 1px); background-size: 28px 28px; mask-image: radial-gradient(ellipse, #000 10%, transparent 72%); }
    .assembly-stage::after { content: ""; position: absolute; left: 50%; top: 2%; width: 1px; height: 96%; background: linear-gradient(transparent, var(--suit-blue), transparent); box-shadow: 0 0 18px var(--suit-blue); opacity: .22; }
    .armor-silhouette { position: absolute; inset: 0; z-index: 1; opacity: 0; filter: drop-shadow(0 0 12px rgba(255,61,66,.18)); }
    .shell-shoulders, .shell-torso, .shell-arm, .shell-pelvis, .shell-leg { position: absolute; background: linear-gradient(145deg, rgba(138,35,45,.98), rgba(63,9,18,.98) 64%, rgba(13,3,9,.99)); border: 1px solid rgba(176,92,69,.58); box-shadow: inset 0 0 18px rgba(255,76,68,.1), inset 0 -12px 18px rgba(0,0,0,.32); }
    .shell-shoulders { left: 14%; top: 22%; width: 72%; height: 18%; clip-path: polygon(14% 0, 86% 0, 100% 46%, 86% 100%, 14% 100%, 0 46%); }
    .shell-torso { left: 25%; top: 24%; width: 50%; height: 40%; clip-path: polygon(18% 0, 82% 0, 100% 20%, 90% 80%, 72% 100%, 28% 100%, 10% 80%, 0 20%); }
    .shell-arm { top: 31%; width: 16%; height: 43%; border-radius: 45% 45% 34% 34%; }
    .shell-arm-left { left: 9%; transform: rotate(8deg); } .shell-arm-right { right: 9%; transform: rotate(-8deg); }
    .shell-pelvis { left: 28%; top: 57%; width: 44%; height: 17%; clip-path: polygon(10% 0, 90% 0, 100% 60%, 76% 100%, 24% 100%, 0 60%); }
    .shell-leg { top: 67%; width: 21%; height: 34%; border-radius: 24% 24% 32% 32%; }
    .shell-leg-left { left: 24%; transform: rotate(3deg); } .shell-leg-right { right: 24%; transform: rotate(-3deg); }
    .armor-silhouette::after { content: ""; position: absolute; left: 49.5%; top: 25%; width: 1px; height: 73%; background: linear-gradient(transparent, rgba(66,217,255,.55), transparent); box-shadow: 0 0 8px rgba(66,217,255,.4); }
    .armor-part { position: absolute; opacity: 0; background: linear-gradient(145deg, #c1554e 0%, #8e1c2a 16%, #5a101a 52%, #17040b 100%); border: 1px solid rgba(255,224,143,.68); box-shadow: inset 0 0 0 1px rgba(255,245,195,.08), inset 0 0 14px rgba(255,89,83,.12), 0 0 8px rgba(255,66,74,.18); }
    .armor-part::after { content: ""; position: absolute; inset: 8%; border: 1px solid rgba(255,224,143,.58); background: repeating-linear-gradient(135deg, transparent 0 9px, rgba(255,226,142,.18) 10px 11px, transparent 12px 20px); opacity: .72; }
    .armor-detail { position: absolute; z-index: 3; opacity: 0; background: linear-gradient(145deg, rgba(214,173,92,.72), rgba(123,25,35,.94) 22%, rgba(54,8,16,.96) 74%); border: 1px solid rgba(255,225,145,.62); box-shadow: inset 0 0 0 1px rgba(255,245,195,.08), inset 0 0 8px rgba(255,71,76,.12), 0 0 5px rgba(255,67,75,.14); }
    .armor-detail::after { content: ""; position: absolute; inset: 14%; border: 1px solid rgba(255,230,155,.58); background: linear-gradient(90deg, transparent 45%, rgba(64,218,255,.75) 48%, rgba(64,218,255,.75) 52%, transparent 55%); box-shadow: 0 0 7px rgba(64,218,255,.35); }
    .arc-reactor { position: absolute; z-index: 12; left: 43%; top: 33%; width: 14%; aspect-ratio: 1; clip-path: polygon(50% 0, 100% 86%, 0 86%); background: linear-gradient(145deg, #ffffff 0%, #a5f2ff 24%, #1da9eb 56%, #06375c 100%); box-shadow: 0 0 8px 3px var(--suit-blue), 0 0 22px 9px rgba(66,217,255,.82), inset 0 0 10px rgba(255,255,255,.95); filter: drop-shadow(0 0 10px var(--suit-blue)); opacity: 1; mix-blend-mode: screen; }
    .arc-reactor::before { content: ""; position: absolute; inset: 14%; clip-path: polygon(50% 0, 100% 86%, 0 86%); background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(66,217,255,.78) 34%, rgba(3,31,58,.96) 78%); }
    .arc-reactor i { position: absolute; z-index: 2; left: 43%; top: 26%; width: 14%; height: 50%; background: #ffffff; box-shadow: 0 0 10px 3px #d9fbff; transform: rotate(0deg); }
    .repulsor { position: absolute; z-index: 20; top: 86%; width: 16%; height: 7%; opacity: 0; border: 1px solid rgba(173,245,255,.78); background: linear-gradient(180deg, #eaffff, #38bfff 42%, #07558d); box-shadow: 0 0 8px 3px var(--suit-blue), 0 0 18px 5px rgba(66,217,255,.58); clip-path: polygon(10% 0, 90% 0, 100% 75%, 70% 100%, 30% 100%, 0 75%); }
    .repulsor-left { left: 26%; } .repulsor-right { right: 26%; }
    .repulsor i { position: absolute; left: 37%; top: 10%; width: 26%; height: 62%; background: #ffffff; box-shadow: 0 0 7px 3px #d7fbff; }
    .repulsor b { position: absolute; left: 16%; top: 72%; width: 68%; height: 230%; opacity: 0; background: linear-gradient(180deg, rgba(234,255,255,.95), rgba(51,195,255,.7) 25%, rgba(15,105,230,.2) 72%, transparent); filter: blur(3px); clip-path: polygon(25% 0, 75% 0, 100% 100%, 0 100%); }
    .flight-ready { position: absolute; z-index: 14; left: 50%; bottom: 4%; transform: translateX(-50%); color: #8deaff; font-size: 10px; letter-spacing: .24em; text-shadow: 0 0 12px #42d9ff; opacity: 0; white-space: nowrap; }
    .suit-overlay.active .arc-reactor { animation: reactor-in .55s .2s cubic-bezier(.2,.8,.2,1) forwards, reactor-beat 1.4s .8s ease-in-out infinite; }
    .suit-overlay.active .repulsor { animation: repulsor-ready .8s 3.8s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .repulsor b { animation: thrust-fire 1.3s 4.5s ease-in-out infinite; }
    .suit-overlay.active .flight-ready { animation: flight-ready-in .8s 4.1s ease-out forwards; }
    .suit-overlay.active .assembly-stage { animation: flight-hover 2.2s 4.6s ease-in-out infinite; }
    .neck { left: 42%; top: 20%; width: 16%; height: 8%; clip-path: polygon(18% 0, 82% 0, 100% 100%, 0 100%); }
    .collar-left, .collar-right { top: 22%; width: 17%; height: 8%; border-color: rgba(255,232,163,.95); }
    .collar-left { left: 27%; transform: rotate(-18deg); clip-path: polygon(0 20%, 100% 0, 84% 100%, 14% 82%); } .collar-right { right: 27%; transform: rotate(18deg); clip-path: polygon(0 0, 100% 20%, 86% 82%, 16% 100%); }
    .chest-left, .chest-right { top: 29%; width: 15%; height: 15%; clip-path: polygon(0 20%, 75% 0, 100% 78%, 28% 100%); }
    .chest-left { left: 14%; transform: rotate(8deg); } .chest-right { right: 14%; transform: scaleX(-1) rotate(8deg); }
    .abdomen-1, .abdomen-2, .abdomen-3 { left: 34%; width: 32%; height: 6%; clip-path: polygon(12% 0, 88% 0, 100% 74%, 78% 100%, 22% 100%, 0 74%); }
    .abdomen-1 { top: 43%; } .abdomen-2 { top: 48%; left: 32%; width: 36%; } .abdomen-3 { top: 53%; }
    .waist-left, .waist-right { top: 55%; width: 15%; height: 11%; clip-path: polygon(0 18%, 100% 0, 86% 100%, 14% 82%); }
    .waist-left { left: 19%; transform: rotate(12deg); } .waist-right { right: 19%; transform: scaleX(-1) rotate(12deg); }
    .bicep-left, .bicep-right { top: 36%; width: 14%; height: 14%; border-radius: 42%; }
    .bicep-left { left: 10%; transform: rotate(15deg); } .bicep-right { right: 10%; transform: rotate(-15deg); }
    .elbow-left, .elbow-right { top: 50%; width: 13%; height: 10%; border-radius: 50%; }
    .elbow-left { left: 8%; transform: rotate(18deg); } .elbow-right { right: 8%; transform: rotate(-18deg); }
    .gauntlet-left, .gauntlet-right { top: 61%; width: 13%; height: 13%; clip-path: polygon(18% 0, 100% 18%, 78% 100%, 0 76%); }
    .gauntlet-left { left: 3%; transform: rotate(18deg); } .gauntlet-right { right: 3%; transform: scaleX(-1) rotate(18deg); }
    .thigh-left, .thigh-right { top: 67%; width: 17%; height: 18%; clip-path: polygon(18% 0, 100% 12%, 78% 100%, 0 82%); }
    .thigh-left { left: 21%; transform: rotate(5deg); } .thigh-right { right: 21%; transform: scaleX(-1) rotate(5deg); }
    .knee-left, .knee-right { top: 79%; width: 17%; height: 10%; border-radius: 42%; clip-path: polygon(8% 10%, 92% 0, 100% 78%, 18% 100%); }
    .knee-left { left: 22%; transform: rotate(3deg); } .knee-right { right: 22%; transform: scaleX(-1) rotate(3deg); }
    .shin-left, .shin-right { top: 85%; width: 14%; height: 14%; clip-path: polygon(12% 0, 88% 10%, 100% 100%, 0 88%); }
    .shin-left { left: 28%; } .shin-right { right: 28%; transform: scaleX(-1); }
    .boot-left, .boot-right { top: 96%; width: 17%; height: 5%; border-color: rgba(255,232,163,.95); clip-path: polygon(0 0, 100% 20%, 88% 100%, 12% 100%); }
    .boot-left { left: 22%; } .boot-right { right: 22%; transform: scaleX(-1); }
    .helmet { left: 35%; top: 3%; width: 30%; height: 20%; border-radius: 48% 48% 42% 42%; clip-path: polygon(20% 0, 80% 0, 100% 34%, 88% 86%, 62% 100%, 38% 100%, 12% 86%, 0 34%); }
    .helmet::before { content: ""; position: absolute; left: 16%; right: 16%; top: 43%; height: 10%; background: var(--suit-blue); box-shadow: 0 0 14px var(--suit-blue), 0 0 24px rgba(66,217,255,.72); clip-path: polygon(0 0, 100% 0, 83% 100%, 17% 100%); }
    .chest { left: 25%; top: 24%; width: 50%; height: 30%; border-radius: 24% 24% 17% 17%; clip-path: polygon(18% 0, 82% 0, 100% 25%, 88% 100%, 12% 100%, 0 25%); }
    .chest::before { display: none; }
    .shoulder-left, .shoulder-right { top: 25%; width: 21%; height: 14%; border-radius: 50% 40% 25% 35%; border-color: var(--suit-gold-bright); }
    .shoulder-left { left: 8%; transform: rotate(-24deg); } .shoulder-right { right: 8%; transform: rotate(24deg); }
    .arm-left, .arm-right { top: 36%; width: 15%; height: 29%; border-radius: 46%; }
    .arm-left { left: 4%; transform: rotate(14deg); } .arm-right { right: 4%; transform: rotate(-14deg); }
    .forearm-left, .forearm-right { top: 59%; width: 13%; height: 22%; border-radius: 40%; }
    .forearm-left { left: 0; transform: rotate(22deg); } .forearm-right { right: 0; transform: rotate(-22deg); }
    .pelvis { left: 31%; top: 52%; width: 38%; height: 16%; border-radius: 18% 18% 35% 35%; border-color: var(--suit-gold-bright); clip-path: polygon(8% 0, 92% 0, 100% 80%, 72% 100%, 28% 100%, 0 80%); }
    .leg-left, .leg-right { top: 66%; width: 18%; height: 30%; border-radius: 18% 18% 38% 38%; }
    .leg-left { left: 27%; border-color: var(--suit-gold-bright); transform: rotate(3deg); } .leg-right { right: 27%; border-color: var(--suit-gold-bright); transform: rotate(-3deg); }
    .assembly-line { position: absolute; left: 15%; right: 15%; bottom: 1%; height: 2px; background: linear-gradient(90deg, transparent, var(--suit-blue), transparent); box-shadow: 0 0 12px var(--suit-blue); transform: scaleX(0); transform-origin: center; }
    .assembly-progress { position: absolute; bottom: 10%; color: #8fdcf3; font-size: 10px; letter-spacing: .22em; }
    .suit-overlay.active .helmet { animation: part-helmet .9s .15s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .shoulder-left, .suit-overlay.active .shoulder-right { animation: part-shoulder .85s .45s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .chest { animation: part-chest 1s .7s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .arm-left, .suit-overlay.active .arm-right { animation: part-arm .95s 1s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .forearm-left, .suit-overlay.active .forearm-right { animation: part-forearm .9s 1.3s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .pelvis { animation: part-pelvis .8s 1.55s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .leg-left, .suit-overlay.active .leg-right { animation: part-leg .95s 1.8s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .assembly-line { animation: line-scan 1.2s 2.4s ease-out forwards; }
    .suit-overlay.active .assembly-progress { animation: progress-pulse 2.2s 2.1s ease-in-out both; }
    .suit-overlay.active .chest::before { animation: core-charge 1.5s 1.5s ease-in-out infinite; }
    .suit-overlay.active .armor-silhouette { animation: silhouette-in .8s .1s cubic-bezier(.2,.8,.2,1) forwards; }
    .suit-overlay.active .armor-detail { animation: detail-in .65s .75s cubic-bezier(.2,.8,.2,1) forwards; }
    .footer { position: absolute; bottom: 3%; left: 50%; transform: translateX(-50%); text-align: center; text-transform: uppercase; width: min(90vw, 720px); }
    .brand { font-size: clamp(22px, 3vw, 38px); font-weight: 700; letter-spacing: .34em; margin-right: -.34em; text-shadow: 0 0 18px rgba(119,245,255,.8); }
    .status { margin-top: 9px; color: var(--cyan); font-size: clamp(12px, 1.3vw, 16px); letter-spacing: .28em; font-weight: 700; text-shadow: 0 0 14px currentColor; transition: color .4s ease; }
    .detail { margin-top: 7px; color: #78aebc; font-size: 11px; letter-spacing: .13em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .signal { position: absolute; top: 3%; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 9px; color: #7eb7c3; font-size: 10px; letter-spacing: .2em; }
    .signal i { width: 7px; height: 7px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 13px var(--cyan); animation: blink 1.5s infinite; }
    body.listening { --cyan: var(--green); --cyan-soft: rgba(67,255,208,.55); }
    body.thinking { --cyan: var(--violet); --cyan-soft: rgba(178,119,255,.55); }
    body.speaking { --cyan: var(--amber); --cyan-soft: rgba(255,211,107,.55); }
    body.thinking .scan { animation-duration: 1.05s; } body.speaking .reactor { animation-duration: 1.1s; }
    @keyframes rotate { to { transform: rotate(360deg); } } @keyframes rotate-reverse { to { transform: rotate(-360deg); } }
    @keyframes breathe { 0%,100% { opacity: .55; transform: scale(.985); } 50% { opacity: 1; transform: scale(1.015); } }
    @keyframes reactor-pulse { 0%,100% { transform: scale(.92); opacity: .76; } 50% { transform: scale(1.07); opacity: 1; } }
    @keyframes blink { 0%,100% { opacity: .35; } 50% { opacity: 1; } }
    @keyframes meter { from { width: 54%; } to { width: 88%; } }
    @keyframes overlay-in { from { opacity: 0; } to { opacity: 1; } }
    @keyframes part-helmet { from { opacity: 0; transform: translateY(-120px) rotate(-18deg) scale(.7); } to { opacity: 1; transform: translateY(0) rotate(0) scale(1); } }
    @keyframes part-shoulder { from { opacity: 0; transform: translateX(var(--from, -100px)) rotate(-30deg); } to { opacity: 1; transform: translateX(0) rotate(0); } }
    @keyframes part-chest { from { opacity: 0; transform: translateY(90px) scale(.65); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes part-arm { from { opacity: 0; transform: translateX(var(--from, -120px)) rotate(30deg); } to { opacity: 1; transform: translateX(0) rotate(0); } }
    @keyframes part-forearm { from { opacity: 0; transform: translateX(var(--from, -150px)) rotate(34deg); } to { opacity: 1; transform: translateX(0) rotate(0); } }
    @keyframes part-pelvis { from { opacity: 0; transform: translateY(100px) scale(.6); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes part-leg { from { opacity: 0; transform: translateY(150px) rotate(12deg); } to { opacity: 1; transform: translateY(0) rotate(0); } }
    @keyframes line-scan { from { transform: scaleX(0); opacity: 0; } 40% { transform: scaleX(1); opacity: 1; } to { transform: scaleX(1); opacity: 0; } }
    @keyframes progress-pulse { 0% { opacity: 0; } 20%,80% { opacity: 1; } 100% { opacity: 0; } }
    @keyframes core-charge { 0%,100% { box-shadow: 0 0 10px 4px var(--suit-blue), 0 0 28px 12px rgba(66,217,255,.42); } 50% { box-shadow: 0 0 18px 7px var(--suit-blue), 0 0 44px 18px rgba(66,217,255,.68); } }
    @keyframes reactor-in { from { opacity: 0; transform: translateY(24px) scale(.35) rotate(-8deg); } to { opacity: 1; transform: translateY(0) scale(1) rotate(0deg); } }
    @keyframes reactor-beat { 0%,100% { filter: drop-shadow(0 0 8px var(--suit-blue)); } 50% { filter: drop-shadow(0 0 18px var(--suit-blue)); } }
    @keyframes repulsor-ready { from { opacity: 0; transform: translateY(10px) scale(.7); } to { opacity: 1; transform: translateY(0) scale(1); } }
    @keyframes thrust-fire { 0%,100% { opacity: .42; transform: scaleY(.72); } 50% { opacity: 1; transform: scaleY(1.18); } }
    @keyframes flight-ready-in { from { opacity: 0; letter-spacing: .05em; } to { opacity: 1; letter-spacing: .24em; } }
    @keyframes flight-hover { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    @keyframes silhouette-in { from { opacity: 0; transform: scale(.92); filter: blur(4px) brightness(1.4); } to { opacity: .94; transform: scale(1); filter: blur(0) brightness(1); } }
    @keyframes detail-in { from { opacity: 0; transform: translateY(8px) scale(.9); filter: brightness(1.5); } to { opacity: 1; transform: translateY(0) scale(1); filter: brightness(1); } }
    @media (max-width: 760px) { .hud { min-height: 520px; } .panel { width: 165px; padding: 11px; transform: scale(.82); } .panel.left { left: -5%; top: 18%; } .panel.right { right: -5%; top: 30%; } .orbital-stage { width: 80vmin; } .core { inset: 30%; } .detail { max-width: 80vw; margin-left: auto; margin-right: auto; } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; } }
  </style>
</head>
<body>
  <main class="hud">
    <span class="corner tl"></span><span class="corner tr"></span><span class="corner bl"></span><span class="corner br"></span>
    <div class="signal"><i></i><span>LOCAL CORE // SECURE CHANNEL</span></div>
    <section class="panel left"><div class="eyebrow">Core diagnostics</div><div class="metric"><span>CPU load</span><strong id="cpu">--</strong></div><div class="meter"><i id="cpu-meter"></i></div><div class="metric"><span>System memory</span><strong id="memory">--</strong></div><div class="metric"><span>Response latency</span><strong id="latency">--</strong></div><div class="metric"><span>Jarvis memory</span><strong id="db">CHECKING</strong></div></section>
    <section class="panel right"><div class="eyebrow">Tactical telemetry</div><div class="metric"><span>Audio channel</span><strong id="audio">STANDBY</strong></div><div class="meter audio-meter"><i id="audio-meter"></i></div><div class="metric"><span>Model link</span><strong id="model">--</strong></div><div class="metric"><span>Network</span><strong id="network">CHECKING</strong></div><div class="meter"><i id="network-meter"></i></div></section>
    <section class="orbital-stage" aria-label="Animated Jarvis reactor HUD">
      <div class="halo"></div><div class="ring one"></div><div class="ring two"></div><div class="ring three"></div><div class="ring four"></div><div class="arc"></div><div class="arc two"></div><div class="ticks"></div><div class="scan"></div><div class="orbit"></div><div class="core"><div class="reactor"></div></div>
    </section>
    <div class="suit-overlay" id="suit-overlay" aria-hidden="true">
      <div class="assembly-label">MARK 50 // ASSEMBLY SEQUENCE</div>
      <div class="assembly-stage">
        <div class="armor-silhouette"><div class="shell-shoulders"></div><div class="shell-torso"></div><div class="shell-arm shell-arm-left"></div><div class="shell-arm shell-arm-right"></div><div class="shell-pelvis"></div><div class="shell-leg shell-leg-left"></div><div class="shell-leg shell-leg-right"></div></div>
        <div class="armor-part helmet"></div>
        <div class="armor-part neck"></div><div class="armor-part collar-left"></div><div class="armor-part collar-right"></div>
        <div class="armor-part chest"></div>
        <div class="arc-reactor"><i></i></div>
        <div class="repulsor repulsor-left"><i></i><b></b></div><div class="repulsor repulsor-right"><i></i><b></b></div>
        <div class="assembly-line"></div>
      </div>
      <div class="assembly-progress">ARC REACTOR // SYSTEMS SYNCHRONIZING</div>
      <div class="flight-ready">FLIGHT SYSTEMS // READY TO FLY</div>
    </div>
    <footer class="footer"><div class="brand">J.A.R.V.I.S.</div><div class="status" id="status">BOOTING</div><div class="detail" id="detail">Initializing local intelligence matrix</div></footer>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    async function refresh() {
      try {
        const response = await fetch('/state?ts=' + Date.now(), { cache: 'no-store' });
        const state = await response.json();
        const status = state.status || 'BOOTING';
        document.body.className = status.toLowerCase();
        updateAnimation(state.animation || 'none');
        $('status').textContent = status;
        $('detail').textContent = state.detail || 'Voice interface online';
        $('audio').textContent = state.mic === 'on' ? 'ACTIVE' : 'STANDBY';
        const telemetry = await (await fetch('/telemetry?ts=' + Date.now(), { cache: 'no-store' })).json();
        $('cpu').textContent = telemetry.cpu_percent.toFixed(1) + '%';
        $('cpu-meter').style.width = Math.max(8, telemetry.cpu_percent) + '%';
        $('memory').textContent = telemetry.memory_used_percent.toFixed(1) + '%';
        $('db').textContent = telemetry.database === 'online' ? 'ONLINE' : 'OFFLINE';
        $('model').textContent = telemetry.model;
        $('network').textContent = telemetry.network;
        $('network-meter').style.width = telemetry.network === 'reachable' ? '100%' : '18%';
        $('audio-meter').style.width = Math.round((telemetry.audio_level || 0) * 100) + '%';
        $('latency').textContent = telemetry.latency_ms === null ? '--' : telemetry.latency_ms + ' ms';
      } catch (_) { /* The HUD keeps animating while the local process restarts. */ }
    }
    let activeAnimation = 'none';
    let animationTimer;
    function updateAnimation(animation) {
      if (animation === activeAnimation) return;
      activeAnimation = animation;
      document.body.classList.toggle('suit-active', animation === 'mark50_assembly');
      const overlay = $('suit-overlay');
      if (!overlay) return;
      overlay.classList.toggle('active', animation === 'mark50_assembly');
      if (animation === 'mark50_assembly') {
        clearTimeout(animationTimer);
        animationTimer = setTimeout(() => {
          document.body.classList.remove('suit-active');
          overlay.classList.remove('active');
                    activeAnimation = animation;
        },
        15000);
      }
    }
    refresh();
    setInterval(refresh, 500);
  </script>
</body>
</html>
"""

STATE = {"status": "BOOTING", "detail": "Starting up", "mic": "off", "latency_ms": None, "audio_level": 0.0, "animation": "none"}
STATE_LOCK = threading.Lock()
SERVER = None
SERVER_STARTED = time.monotonic()
_AUDIO_QUEUE: queue.Queue[float] = queue.Queue(maxsize=1)
_AUDIO_WRITER_STARTED = False
_AUDIO_WRITER_LOCK = threading.Lock()
_STATE_WRITE_QUEUE: queue.Queue[bool] = queue.Queue(maxsize=1)
_STATE_WRITER_STARTED = False
_STATE_WRITER_LOCK = threading.Lock()
_STATE_LOADED = False
_TELEMETRY_CACHE: dict[str, object] | None = None
_TELEMETRY_CACHE_AT = 0.0
_TELEMETRY_CACHE_LOCK = threading.Lock()


def collect_telemetry() -> dict[str, object]:
    """Collect lightweight, local-only telemetry for the HUD."""
    global _TELEMETRY_CACHE, _TELEMETRY_CACHE_AT
    now = time.monotonic()
    with _TELEMETRY_CACHE_LOCK:
        if _TELEMETRY_CACHE is not None and now - _TELEMETRY_CACHE_AT < 0.75:
            return dict(_TELEMETRY_CACHE)

    cpu_count = os.cpu_count() or 1
    try:
        cpu_percent = min(100.0, max(0.0, os.getloadavg()[0] / cpu_count * 100.0))
    except (AttributeError, OSError):
        cpu_percent = 0.0

    memory_used_percent = 0.0
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0])
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", values.get("MemFree", 0))
        if total:
            memory_used_percent = (total - available) / total * 100.0
    except (FileNotFoundError, ValueError):
        pass

    database = "offline"
    db_path = os.getenv("JARVIS_DB_PATH", "jarvis_history.sqlite3")
    try:
        with sqlite3.connect(db_path, timeout=0.2) as connection:
            connection.execute("SELECT 1").fetchone()
        database = "online"
    except sqlite3.Error:
        pass

    network = "unreachable"
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=0.2):
            network = "reachable"
    except OSError:
        pass

    with STATE_LOCK:
        latency_ms = STATE.get("latency_ms")

    result = {
        "cpu_percent": round(cpu_percent, 1),
        "memory_used_percent": round(memory_used_percent, 1),
        "database": database,
        "model": os.getenv("JARVIS_MODEL", "gemini-flash-latest"),
        "network": network,
        "latency_ms": latency_ms,
        "audio_level": round(float(STATE.get("audio_level", 0.0)), 3),
        "platform": platform.system(),
        "uptime_seconds": round(time.monotonic() - SERVER_STARTED),
    }
    with _TELEMETRY_CACHE_LOCK:
        _TELEMETRY_CACHE = result
        _TELEMETRY_CACHE_AT = time.monotonic()
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/telemetry"):
            payload = json.dumps(collect_telemetry()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/shutdown"):
            self.send_response(200)
            self.end_headers()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path.startswith("/state"):
            with STATE_LOCK:
                if STATE_FILE.exists():
                    try:
                        STATE.update(json.loads(STATE_FILE.read_text()))
                    except Exception:
                        pass
                payload = json.dumps(STATE).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _state_writer() -> None:
    """Persist the newest HUD state off the voice loop."""
    while True:
        _STATE_WRITE_QUEUE.get()
        try:
            with STATE_LOCK:
                state = dict(STATE)
                temp_file = STATE_FILE.with_suffix(".tmp")
                temp_file.write_text(json.dumps(state))
                temp_file.replace(STATE_FILE)
        except Exception:
            pass


def _queue_state_write() -> None:
    global _STATE_WRITER_STARTED
    with _STATE_WRITER_LOCK:
        if not _STATE_WRITER_STARTED:
            threading.Thread(target=_state_writer, name="jarvis-state-writer", daemon=True).start()
            _STATE_WRITER_STARTED = True
    try:
        _STATE_WRITE_QUEUE.put_nowait(True)
    except queue.Full:
        pass


def set_state(status: str | None = None, detail: str | None = None, mic: str | None = None, latency_ms: int | None = None, animation: str | None = None) -> None:
    global _STATE_LOADED
    with STATE_LOCK:
        if not _STATE_LOADED and STATE_FILE.exists():
            try:
                STATE.update(json.loads(STATE_FILE.read_text()))
            except Exception:
                pass
            _STATE_LOADED = True
        if status is not None:
            STATE["status"] = status
        if detail is not None:
            STATE["detail"] = detail
        if mic is not None:
            STATE["mic"] = mic
        if latency_ms is not None:
            STATE["latency_ms"] = latency_ms
        if animation is not None:
            STATE["animation"] = animation
    _queue_state_write()


def _audio_state_writer() -> None:
    """Persist only the newest audio level off the microphone read path."""
    while True:
        level = _AUDIO_QUEUE.get()
        try:
            with STATE_LOCK:
                state = dict(STATE)
                if STATE_FILE.exists():
                    try:
                        state.update(json.loads(STATE_FILE.read_text()))
                    except Exception:
                        pass
                state["audio_level"] = level
                temp_file = STATE_FILE.with_suffix(".tmp")
                temp_file.write_text(json.dumps(state))
                temp_file.replace(STATE_FILE)
        except Exception:
            pass


def set_audio_level(level: float) -> None:
    """Queue normalized microphone intensity without blocking audio capture."""
    global _AUDIO_WRITER_STARTED
    normalized = max(0.0, min(1.0, float(level)))
    with _AUDIO_WRITER_LOCK:
        if not _AUDIO_WRITER_STARTED:
            threading.Thread(target=_audio_state_writer, name="jarvis-audio-state", daemon=True).start()
            _AUDIO_WRITER_STARTED = True
    try:
        _AUDIO_QUEUE.get_nowait()
    except queue.Empty:
        pass
    try:
        _AUDIO_QUEUE.put_nowait(normalized)
    except queue.Full:
        pass


def _open_browser(url: str) -> None:
    import webbrowser
    webbrowser.open(url)


def run_server() -> int:
    global SERVER
    SERVER = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    port = SERVER.server_address[1]
    PORT_FILE.write_text(str(port))
    _open_browser(f"http://127.0.0.1:{port}/")
    SERVER.serve_forever()
    SERVER.server_close()
    return port


def shutdown_server(port: int) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/shutdown", timeout=2).read()
    except Exception:
        pass


def get_running_port() -> int | None:
    try:
        return int(PORT_FILE.read_text().strip())
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shutdown", type=int)
    parser.add_argument("--set-status")
    parser.add_argument("--set-detail")
    parser.add_argument("--mic")
    parser.add_argument("--latency-ms", type=int)
    args = parser.parse_args()
    if args.shutdown:
        shutdown_server(args.shutdown)
        return
    if args.set_status or args.set_detail or args.mic or args.latency_ms is not None:
        set_state(args.set_status, args.set_detail, args.mic, args.latency_ms)
        return
    run_server()


if __name__ == "__main__":
    main()
