export type StandardSection = string;

export type StandardDoc = {
  id: string;
  title: string;
  sections: string[];
  content: string;
};

export async function getStandards(): Promise<{ standards: StandardDoc[] }> {
  const res = await fetch("/api/v1/standards", { credentials: "include" });
  if (!res.ok) throw new Error(`Failed to load standards: ${res.status}`);
  return res.json();
}
