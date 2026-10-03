export type Card = {
  id: string;
  title: string;
  details: string;
};

export type Column = {
  id: string;
  name: string;
  cards: Card[];
};

const demoCards: Card[] = [
  {
    id: 'card-brief',
    title: 'Shape the product brief',
    details: 'Turn the strongest customer needs into a focused one-page brief.'
  },
  {
    id: 'card-research',
    title: 'Review interview notes',
    details: 'Pull out recurring themes and questions for the next sprint.'
  },
  {
    id: 'card-prototype',
    title: 'Prototype the board flow',
    details: 'Try the quickest path from a new card to a completed task.'
  },
  {
    id: 'card-release',
    title: 'Prepare release notes',
    details: 'Capture the decisions and improvements that matter to the team.'
  }
];

export function createDemoBoard(): Column[] {
  return [
    { id: 'backlog', name: 'Backlog', cards: [demoCards[0]] },
    { id: 'planned', name: 'Planned', cards: [demoCards[1]] },
    { id: 'progress', name: 'In progress', cards: [demoCards[2]] },
    { id: 'review', name: 'Review', cards: [] },
    { id: 'done', name: 'Done', cards: [demoCards[3]] }
  ];
}

export function createCard(title: string, details: string, id?: string): Card {
  return { id: id ?? crypto.randomUUID(), title: title.trim(), details: details.trim() };
}
