import { describe, expect, it } from 'vitest';
import { createCard, createDemoBoard } from './board';

describe('board data', () => {
  it('starts with one board made of five fixed columns and demo cards', () => {
    const board = createDemoBoard();

    expect(board).toHaveLength(5);
    expect(board.map((column) => column.name)).toEqual([
      'Backlog',
      'Planned',
      'In progress',
      'Review',
      'Done'
    ]);
    expect(board.flatMap((column) => column.cards)).toHaveLength(4);
  });

  it('trims new card content', () => {
    expect(createCard('  Plan launch  ', '  Confirm owners  ', 'test-id')).toEqual({
      id: 'test-id',
      title: 'Plan launch',
      details: 'Confirm owners'
    });
  });
});
