(function(){
    'use strict';

    const board = document.getElementById('board');
    if(!board || board.dataset.connectionDoubleClickBound === '1') return;
    board.dataset.connectionDoubleClickBound = '1';

    board.addEventListener('dblclick', event => {
        if(event.button !== 0) return;
        const hit = event.target?.closest?.('.link-hit[data-connection-id]');
        const connectionId = hit?.dataset?.connectionId || '';
        if(!connectionId || !board.contains(hit) || typeof deleteConnection !== 'function') return;
        event.preventDefault();
        event.stopPropagation();
        deleteConnection(connectionId, event);
    });
})();
