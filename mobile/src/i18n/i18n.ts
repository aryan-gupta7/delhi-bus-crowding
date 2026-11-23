import data from "./strings.json";

export type Lang = "en" | "hi";
type Table = Record<string, string>;

/** Strings that exist only in the app. Everything else comes from web/i18n.js through strings.json. */
const APP: Record<Lang, Table> = {
  en: {
    tabPlan: "Plan", tabMap: "Map", tabAbout: "About", back: "Back", results: "Results",
    lastResult: "Last result", offlineCached: "No connection. Showing your last result.",
    server: "Server address", serverHint: "Address of the planner API, for example http://192.168.1.20:8000.",
    save: "Save", saved: "Saved", settings: "Settings", noPlanYet: "Plan a trip first and its stretches appear here.",
    timeInvalid: "Enter the time as HH:MM, for example 08:57.", earlier: "15 min earlier", laterBy: "15 min later",
    seeDetails: "See along the ride", whichDay: "Which day", mapTitle: "Journey map",
    schematicNote: "Schematic: no street map is loaded. Line width shows relative sampled riders.",
    leavingIn: "Leaving {n} min later", arrivesLater: "arrives about {n} min later",
  },
  hi: {
    tabPlan: "यात्रा", tabMap: "नक्शा", tabAbout: "जानकारी", back: "वापस", results: "नतीजे",
    lastResult: "पिछला नतीजा", offlineCached: "कनेक्शन नहीं है। आपका पिछला नतीजा दिख रहा है।",
    server: "सर्वर का पता", serverHint: "प्लानर API का पता, जैसे http://192.168.1.20:8000।",
    save: "सहेजें", saved: "सहेजा गया", settings: "सेटिंग", noPlanYet: "पहले यात्रा चुनें, फिर उसके हिस्से यहाँ दिखेंगे।",
    timeInvalid: "समय HH:MM में लिखें, जैसे 08:57।", earlier: "15 मिनट पहले", laterBy: "15 मिनट बाद",
    seeDetails: "रास्ते का ब्यौरा", whichDay: "कौन सा दिन", mapTitle: "यात्रा का नक्शा",
    schematicNote: "सांकेतिक नक्शा: सड़कें नहीं दिखाई गई हैं। रेखा की चौड़ाई सैंपल सवारियों के अनुपात में है।",
    leavingIn: "{n} मिनट बाद निकलें", arrivesLater: "लगभग {n} मिनट देर से पहुँचेंगे",
  },
};

const WEB = data.STRINGS as Record<Lang, Table>;

export function translate(lang: Lang, key: string, vars: Record<string, string | number> = {}): string {
  const raw = APP[lang][key] ?? WEB[lang][key] ?? APP.en[key] ?? WEB.en[key] ?? key;
  return raw.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? ""));
}

export type T = (key: string, vars?: Record<string, string | number>) => string;
