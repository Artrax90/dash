import pytest
from pathlib import Path

def test_index_html_pre_hydration_theme_script():
    index_html = Path("index.html").read_text(encoding="utf-8")
    assert "wm_theme" in index_html, "index.html must check wm_theme in localStorage to prevent flash of light theme"
    assert "classList.add('dark')" in index_html or "classList.add(\"dark\")" in index_html, "index.html must apply dark class prior to hydration"

def test_app_theme_persistence_in_localstorage():
    app_tsx = Path("src/App.tsx").read_text(encoding="utf-8")
    
    # 1. State must read wm_theme
    assert "localStorage.getItem('wm_theme')" in app_tsx, "App.tsx must read wm_theme on init"
    
    # 2. Must save wm_theme on toggle or state change
    assert "localStorage.setItem('wm_theme'" in app_tsx or 'localStorage.setItem("wm_theme"' in app_tsx, "App.tsx must persist wm_theme to localStorage"
    
    # 3. Must sync dark class to documentElement or body
    assert "document.documentElement.classList" in app_tsx or "document.body.classList" in app_tsx, "App.tsx must sync dark class to documentElement/body"
    
    # 4. Must sync storage events across browser tabs
    assert "storage" in app_tsx and "wm_theme" in app_tsx, "App.tsx should listen to storage events to sync theme across tabs"

def test_index_css_dark_theme_root_support():
    css = Path("src/index.css").read_text(encoding="utf-8")
    assert ".app.dark" in css, "CSS must define .app.dark"
    assert "html.dark" in css or "body.dark" in css, "CSS should have background for html.dark or body.dark to prevent white background bounce"
