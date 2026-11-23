// Single source of UI strings is web/i18n.js. This writes src/i18n/strings.json from it
// (run with: bun run sync:strings). With --check it only reports whether the file is current.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../../web/i18n.js", import.meta.url), "utf8");
const context = {};
vm.runInNewContext(source + "\nthis.out = { STRINGS, API_MESSAGES };", context);
const json = JSON.stringify(context.out, null, 2) + "\n";
const target = new URL("../src/i18n/strings.json", import.meta.url);
if (process.argv.includes("--check")) {
  const same = existsSync(target) && readFileSync(target, "utf8") === json;
  console.log(same ? "strings.json is current" : "strings.json is OUT OF DATE: run `bun run sync:strings`");
  process.exit(same ? 0 : 1);
}
writeFileSync(target, json);
console.log("wrote src/i18n/strings.json");
