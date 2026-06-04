"""Oracle Fusion UI locators."""

LOGIN = {
    "username": [
        "#userid", 
        "input[name='username']",
        "input[autocomplete='username']",
        "input[name='userid']", 
        "input[type='text']:visible"
    ],
    "password": [
        "#password", 
        "input[name='password']",
        "input[autocomplete='current-password']",
        "input[type='password']"
    ],
    "next_btn": [
        "button:has-text('Next')",
        "#idcs-signin-basic-signin-form-submit",
        "button[type='submit']:has-text('Next')",
        "[id*='next']",
        ".idcs-signin-button"
    ],
    "submit": [
        "#btnActive", 
        "button[type='submit']", 
        "input[type='submit']",
        "button:has-text('Sign In')",
        "button:has-text('Sign in')",
        "button:has-text('Login')",
        "button:has-text('Submit')",
        ".idcs-button",
        "[class*='signin-button']",
        "[id*='signin']",
        "[id*='submit']"
    ]
}

HOME_LANDMARKS = [
    "[title='Home']", 
    "[aria-label='Home']",
    "a[title='Settings and Actions']",
    "[aria-label='Navigator']", 
    "button[title='Navigator']",
    "text=/Welcome,/i"
]

SPINNERS = [
    "div.AFLoadingBlock", 
    "[aria-busy='true']",
    ".AFLogo[role='progressbar']", 
    ".oj-progress-circle",
    ".oj-conveyor-belt-item.oj-selected:visible"
]
