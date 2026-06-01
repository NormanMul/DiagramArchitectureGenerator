export interface Node {
  id: string;
  label: string;
  icon_id: string;
  tier: string;
}

export interface Edge {
  source: string;
  target: string;
  label?: string;
  style?: "solid" | "dashed" | "dotted";
}

export interface PopulatedPattern {
  pattern_name: string;
  title: string;
  source_url?: string | null;
  tiers: string[];
  nodes: Node[];
  edges: Edge[];
  well_architected_notes?: string;
}

export interface DiagramArtifact {
  kind: "svg" | "png" | "drawio" | "py";
  url: string;
  bytes_size: number;
}

export interface GenerateResponse {
  session_id: string;
  diagram_id: string;
  pattern: PopulatedPattern;
  justification: string;
  candidate_pattern_names: string[];
  artifacts: DiagramArtifact[];
  tokens_input: number;
  tokens_output: number;
}

export interface RefineResponse {
  session_id: string;
  diagram_id: string;
  pattern: PopulatedPattern;
  summary: string;
  artifacts: DiagramArtifact[];
  tokens_input: number;
  tokens_output: number;
}
