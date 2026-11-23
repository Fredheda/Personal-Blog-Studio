# Development notes

## Effects

Components do not call `useEffect`, `useLayoutEffect` or `useInsertionEffect`: ESLint rejects the import and `React.useEffect`. The one exempt folder is `frontend/effects/`; its hooks are named for what they synchronise with. Add a hook there only for a new thing outside React, with its test.

| You wanted an effect to | Do this |
|---|---|
| compute something from props or state | compute it during render (`useMemo` only if measured slow) |
| react to a user action | do it in the event handler |
| reset state when an id changes | give the component `key={id}` |
| tell the parent about a change | call the parent's callback in the same handler that changed the state |
| keep the latest callback for a listener or timer | `useLatest` |
| focus an element when it appears, and give the focus back | `useFocusReturn`, or focus in the handler that showed it |
| listen to the window | `useWindowListener` |
| run a timer | `useInterval` |
| load data when something shows or changes | `useRequest` |
| own an object with a close step (the autosave controller) | `useController` |
| mount a third-party widget on a DOM node | `useWidget` |
| subscribe to a store | `useSyncExternalStore` |
