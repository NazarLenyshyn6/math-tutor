export interface DocumentRef {
  document_name: string;
  page: number;
}

export interface Interaction {
  user: string;
  assistant: string;
  documents: DocumentRef[];
}

export interface DocumentInfo {
  name: string;
  user_description: string;
}
