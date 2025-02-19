import os
import asyncio
import random
import logging
from playwright.async_api import async_playwright

async def login_to_google(page):
    """
    Logs in to Google using credentials from the environment variables GOOGLE_USER and GOOGLE_PW.
    Human-like delays and mouse movements are added to mimic real user interactions.
    """
    username = os.getenv("GOOGLE_USER")
    password = os.getenv("GOOGLE_PW")
    if not username or not password:
        raise Exception("Missing GOOGLE_USER or GOOGLE_PW environment variable")
    
    logging.info("Navigating to Google login page...")
    await page.goto("https://accounts.google.com/ServiceLogin")
    
    # Wait for email field and fill it with a random delay
    await page.wait_for_selector("input[type='email']", timeout=10000)
    await page.wait_for_timeout(random.randint(500, 1500))
    await page.fill("input[type='email']", username)
    await page.wait_for_timeout(random.randint(300, 700))
    await page.click("#identifierNext")
    
    await page.wait_for_timeout(random.randint(2000, 3000))
    
    # Wait for password field and fill it
    await page.wait_for_selector("input[type='password']", timeout=10000)
    await page.wait_for_timeout(random.randint(500, 1500))
    await page.fill("input[type='password']", password)
    await page.wait_for_timeout(random.randint(300, 700))
    await page.click("#passwordNext")
    
    # Wait for successful login by checking that the email field is no longer visible
    await page.wait_for_timeout(random.randint(5000, 7000))
    if await page.query_selector("input[type='email']") is not None:
        raise Exception("Login failed; email input still present.")
    
    logging.info("Google login successful.")
    return page

async def human_like_mouse_move(page, start, end):
    """
    Simulates a human-like mouse movement from the start position to the end position.
    """
    steps = random.randint(10, 20)
    dx = (end[0] - start[0]) / steps
    dy = (end[1] - start[1]) / steps
    x, y = start
    for i in range(steps):
        x += dx + random.uniform(-2, 2)
        y += dy + random.uniform(-2, 2)
        await page.mouse.move(x, y)
        await page.wait_for_timeout(random.randint(50, 150))
    await page.mouse.move(end[0], end[1])
