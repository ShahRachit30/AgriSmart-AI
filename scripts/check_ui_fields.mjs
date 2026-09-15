#!/usr/bin/env node
/**
 * Optional-field check: can a typo in a soil/weather box stop a farmer from
 * analysing a perfectly good leaf photo?
 *
 * Why this exists
 * ---------------
 * Every field on the analyse card is optional context, but FastAPI parses them as
 * `float` and the endpoint hard-rejects out-of-range soil values with 422. Before
 * app/frontend/src/fields.mjs existed, typing "7,5" (comma decimal - the natural way
 * to write it on a phone keyboard that offers a comma) or "NA" in soil pH made
 * POST /api/analyze answer 422 "Some values are missing or out of range" and the
 * farmer got an error instead of a diagnosis for a healthy photo.
 *
 * This asserts the normaliser drops/normalises exactly what the API would reject,
 * keeps everything else, and never invents a value.
 *
 * Run:  node scripts/check_ui_fields.mjs      (exit 0 = safe, 1 = a typo can block)
 */
import { cleanNumericFields, parseNumber, parseBool } from "../app/frontend/src/fields.mjs";

const problems = [];
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "✓" : "✗"} ${label} -> ${JSON.stringify(got)}${ok ? "" : ` (want ${JSON.stringify(want)})`}`);
  if (!ok) problems.push(label);
};

console.log("optional-field check - can a typo block the diagnosis?");

console.log("\nparseNumber - what the farmer typed -> number");
check('"7,5" (comma decimal)', parseNumber("7,5"), 7.5);
check('"7.5"', parseNumber("7.5"), 7.5);
check('" 12 cm " (unit)', parseNumber("12 cm"), 12);
check('"45 %"', parseNumber("45 %"), 45);
check('"abc" (unusable)', Number.isNaN(parseNumber("abc")), true);
check('"" (blank)', parseNumber(""), null);
check("12 (already a number)", parseNumber(12), 12);

console.log("\nparseBool - use_sensors reaches the API as a real boolean");
check('"maybe" -> default', parseBool("maybe", true), true);
check('"false" -> false', parseBool("false"), false);
check("true -> true", parseBool(true), true);

console.log("\ncleanNumericFields - a typo never blocks, good values survive");
const typo = cleanNumericFields({ soil_ph: "7,5", temperature: "28", nitrogen: "NA", area_ha: "2" });
check("comma decimal is kept and fixed", typo.values.soil_ph, 7.5);
check("good values survive", [typo.values.temperature, typo.values.area_ha], [28, 2]);
check("unusable value is dropped, not invented", typo.values.nitrogen, "");
check("dropped list names the field", typo.dropped, ["nitrogen"]);

const outOfRange = cleanNumericFields({ soil_ph: "999", soil_moisture_pct: "-3" });
check("out-of-range soil pH dropped (server 422s it)", outOfRange.values.soil_ph, "");
check("out-of-range moisture dropped", outOfRange.values.soil_moisture_pct, "");
check("both reported", outOfRange.dropped.sort(), ["soil_moisture_pct", "soil_ph"]);

const blank = cleanNumericFields({ soil_ph: "", area_ha: "" });
check("blank stays blank (optional context)", [blank.values.soil_ph, blank.values.area_ha], ["", ""]);
check("blank is not an error", blank.dropped, []);

const boundary = cleanNumericFields({ soil_ph: "14", soil_moisture_pct: "100" });
check("range edges are accepted", [boundary.values.soil_ph, boundary.values.soil_moisture_pct], [14, 100]);

const untouched = cleanNumericFields({});
check("no fields -> nothing dropped", untouched.dropped, []);

if (problems.length) {
  console.error(`\n✗ ${problems.length} problem(s): ${problems.join(", ")}`);
  process.exit(1);
}
console.log("\n✓ a typo in an optional field can no longer block a leaf diagnosis");
