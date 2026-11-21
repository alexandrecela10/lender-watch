// The Excel formula =LW.CHECK(A2:A6, [as_of]). It asks the Lender Watch service, signed in through the panel.
"use strict";

async function check(names, asOf) {
  const cells = ErmExcel.namesFromRange(names);
  const wanted = [...new Set(cells.filter(Boolean))];
  if (!wanted.length) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, "Select cells with company names.");
  }
  let rows;
  try {
    rows = await LwApi.check(wanted, asOf);
  } catch (error) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, error.message);
  }
  return ErmExcel.spillRows(cells, rows);
}

CustomFunctions.associate("CHECK", check);

// =LW.MEASURE(measure, names, [as_of]): the prototype's agreed measures, on this computer only.
async function measure(name, names, asOf) {
  const cells = ErmExcel.namesFromRange(names);
  const wanted = [...new Set(cells.filter(Boolean))];
  if (!wanted.length) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, "Select cells with company names.");
  }
  let out;
  try {
    out = await LwApi.post("/api/measure", { measure: name, companies: wanted, as_of: asOf || null });
  } catch (error) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, error.message);
  }
  return ErmExcel.spillMeasure(cells, wanted, out.rows);
}

CustomFunctions.associate("MEASURE", measure);
