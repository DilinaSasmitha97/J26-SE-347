import "@testing-library/jest-dom/vitest";

// jsdom has no scrolling; the router scrolls to the top on navigation.
window.scrollTo = () => {};
