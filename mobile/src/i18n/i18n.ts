import data from "./strings.json";

export type Lang = "en" | "hi";
type Table = Record<string, string>;

/** Strings that exist only in the app. Everything else comes from web/i18n.js through strings.json. */
const APP: Record<Lang, Table> = {
  en: {
    tabPlan: "Plan", tabMap: "Map", tabAbout: "About", back: "Back", lastResult: "Last result", offlineCached: "No connection. Showing your last result.",
    server: "Server address", serverHint: "Address of the planner API, for example http://192.168.1.20:8000.",
    save: "Save", saved: "Saved", settings: "Settings", noPlanYet: "Plan a trip first and its stretches appear here.",
    whichDay: "Which day", mapTitle: "Journey map",
    schematicNote: "Schematic: no street map is loaded. Line width shows relative sampled riders.",
    leavingIn: "Leaving {n} min later", arrivesLater: "arrives about {n} min later",
    useLocation: "Use my location", pickOnMap: "Pick on map", nearYou: "Near you", allStops: "All stops, A to Z",
    locating: "Finding the nearest stop…", locationDenied: "Location is off for this app. Allow it in the phone's settings, or pick a stop from the list.",
    locationFailed: "Could not get your location. Pick a stop from the list.", nearestHint: "Nearest stop to you, {d} away", nearestFar: "You are {d} from the nearest Delhi bus stop. Choose a stop from the list.",
    selectStop: "Select this stop", mapPickTitle: "Choose a stop on the map", mapPickHint: "Tap a dot to see the stop.", mapLoading: "Loading stops…",
    timeNow: "Now", timeIn30: "In 30 min", timeIn60: "In 1 hour", pickTime: "Pick time", loadMore: "Show more stops",
    noMatch: "No matching stop.", serverDown: "Cannot reach the planner server. Check the phone is on the same Wi-Fi (or the USB cable) and the Server address under About.", close: "Close",
  },
  hi: {
    tabPlan: "यात्रा", tabMap: "नक्शा", tabAbout: "जानकारी", back: "वापस", lastResult: "पिछला नतीजा", offlineCached: "कनेक्शन नहीं है। आपका पिछला नतीजा दिख रहा है।",
    server: "सर्वर का पता", serverHint: "प्लानर API का पता, जैसे http://192.168.1.20:8000।",
    save: "सहेजें", saved: "सहेजा गया", settings: "सेटिंग", noPlanYet: "पहले यात्रा चुनें, फिर उसके हिस्से यहाँ दिखेंगे।",
    whichDay: "कौन सा दिन", mapTitle: "यात्रा का नक्शा",
    schematicNote: "सांकेतिक नक्शा: सड़कें नहीं दिखाई गई हैं। रेखा की चौड़ाई सैंपल सवारियों के अनुपात में है।",
    leavingIn: "{n} मिनट बाद निकलें", arrivesLater: "लगभग {n} मिनट देर से पहुँचेंगे",
    useLocation: "मेरी लोकेशन से चुनें", pickOnMap: "नक्शे पर चुनें", nearYou: "आपके पास", allStops: "सभी स्टॉप, क से ज्ञ",
    locating: "सबसे पास का स्टॉप खोज रहे हैं…", locationDenied: "इस ऐप के लिए लोकेशन बंद है। फ़ोन की सेटिंग में अनुमति दें, या सूची से स्टॉप चुनें।",
    locationFailed: "आपकी लोकेशन नहीं मिली। सूची से स्टॉप चुनें।", nearestHint: "आपके सबसे पास का स्टॉप, {d} दूर", nearestFar: "आप दिल्ली के सबसे पास के बस स्टॉप से {d} दूर हैं। सूची से स्टॉप चुनें।",
    selectStop: "यह स्टॉप चुनें", mapPickTitle: "नक्शे पर स्टॉप चुनें", mapPickHint: "स्टॉप देखने के लिए बिंदु पर दबाएँ।", mapLoading: "स्टॉप लोड हो रहे हैं…",
    timeNow: "अभी", timeIn30: "30 मिनट बाद", timeIn60: "1 घंटे बाद", pickTime: "समय चुनें", loadMore: "और स्टॉप दिखाएँ",
    noMatch: "कोई स्टॉप नहीं मिला।", serverDown: "प्लानर सर्वर तक नहीं पहुँच पा रहे। फ़ोन उसी वाई-फ़ाई (या USB केबल) पर है और जानकारी में सर्वर का पता सही है, यह देखें।", close: "बंद करें",
  },
};

const WEB = data.STRINGS as Record<Lang, Table>;

export function translate(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const raw = APP[lang][key] ?? WEB[lang][key] ?? APP.en[key] ?? WEB.en[key] ?? key;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? ""));
}

export type T = (key: string, vars?: Record<string, string | number>) => string;
