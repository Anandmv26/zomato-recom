// Animated food spinner shown while the API/LLM loads
export default function FoodSpinner() {
    return (
        <div className="food-spinner-wrapper" role="status" aria-live="polite">
            <span className="food-spinner" aria-hidden="true">🍽️</span>
            <p className="spinner-text">Our AI chef is picking the best restaurants&hellip;</p>
        </div>
    );
}
