import { useNavigate } from 'react-router-dom';
import StrategyForm from '../components/StrategyForm';

function StrategyCreate() {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Create New Strategy</h1>
        <button
          onClick={() => navigate('/strategies')}
          className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors"
        >
          Back to Strategies
        </button>
      </div>

      <StrategyForm
        mode="create"
        onSuccess={() => navigate('/strategies')}
        onCancel={() => navigate('/strategies')}
      />
    </div>
  );
}

export default StrategyCreate;
