const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const dates = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export function formatInr(value) {
  return `Rs ${rupees.format(value)}`;
}

export function formatDate(value) {
  return dates.format(new Date(`${value}T00:00:00Z`));
}
