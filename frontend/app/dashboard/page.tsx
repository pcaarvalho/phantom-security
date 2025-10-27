'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { apiClient } from '@/lib/api-client';
import { useWebSocket, useScanProgress } from '@/hooks/use-websocket';
import { toast } from 'sonner';

interface Scan {
  id: number;
  target: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  risk_score?: number;
  vulnerability_count?: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  scan_type: string;
}

interface ScanStatistics {
  total_scans: number;
  completed_scans: number;
  failed_scans: number;
  processing_scans: number;
  average_risk_score: number;
  total_vulnerabilities_found: number;
  success_rate: number;
}

export default function Dashboard() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [stats, setStats] = useState<ScanStatistics | null>(null);
  const [target, setTarget] = useState('');
  const [loading, setLoading] = useState(false);
  const [activeScanId, setActiveScanId] = useState<number | null>(null);
  
  const { isConnected, connectionStatus, addMessageListener } = useWebSocket();
  const { progress, status, phase } = useScanProgress(activeScanId);

  // Load scans and statistics
  const loadData = async () => {
    try {
      const [scansData, statsData] = await Promise.all([
        apiClient.getScans(),
        apiClient.getScanStatistics()
      ]);
      
      setScans(scansData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load scan data');
    }
  };

  useEffect(() => {
    loadData();
    
    // Refresh data every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Listen for WebSocket updates
  useEffect(() => {
    if (!isConnected) return;

    const removeListener = addMessageListener((message) => {
      if (message.type === 'scan_completed' || message.type === 'scan_failed') {
        // Refresh scans when any scan completes or fails
        loadData();
        
        // Clear active scan if it's the one that completed/failed
        if (message.scan_id === activeScanId) {
          setActiveScanId(null);
        }
      }
    });

    return removeListener;
  }, [isConnected, addMessageListener, activeScanId]);

  const startScan = async () => {
    if (!target.trim()) return;
    
    setLoading(true);
    
    try {
      const result = await apiClient.createScan(target.trim());
      
      setActiveScanId(result.id);
      setTarget('');
      
      // Add the new scan to the list immediately
      const newScan: Scan = {
        id: result.id,
        target: result.target,
        status: 'pending' as const,
        created_at: result.created_at,
        started_at: result.started_at,
        scan_type: result.scan_type,
      };
      
      setScans([newScan, ...scans]);
      
      toast.success(`Scan started for ${target.trim()}`);
      
    } catch (error) {
      console.error('Scan failed to start:', error);
      toast.error('Failed to start scan: ' + (error as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleViewReport = async (scanId: number) => {
    try {
      // Navigate to detailed report view (we'll implement this page later)
      window.open(`/reports/${scanId}`, '_blank');
    } catch (error) {
      console.error('Failed to view report:', error);
      toast.error('Failed to open report');
    }
  };

  const handleDownloadPDF = async (scanId: number) => {
    try {
      toast.info('Generating PDF report...');
      
      const blob = await apiClient.getReportPDF(scanId);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      
      // Get scan info for filename
      const scan = scans.find(s => s.id === scanId);
      const filename = scan 
        ? `phantom_security_report_${scan.target.replace(/[^a-zA-Z0-9]/g, '_')}_${scanId}.pdf`
        : `phantom_security_report_${scanId}.pdf`;
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast.success('PDF report downloaded successfully');
      
    } catch (error) {
      console.error('Failed to download PDF:', error);
      toast.error('Failed to download PDF report');
    }
  };

  const getRiskColor = (riskScore?: number) => {
    if (!riskScore) return 'text-gray-400';
    if (riskScore >= 76) return 'text-red-500';
    if (riskScore >= 51) return 'text-orange-500';
    if (riskScore >= 26) return 'text-yellow-500';
    return 'text-green-500';
  };

  const getRiskLevel = (riskScore?: number) => {
    if (!riskScore) return 'Unknown';
    if (riskScore >= 76) return 'Critical';
    if (riskScore >= 51) return 'High';
    if (riskScore >= 26) return 'Medium';
    return 'Low';
  };

  // Calculate display statistics
  const displayStats = stats ? {
    totalScans: stats.total_scans,
    completedScans: stats.completed_scans,
    totalVulnerabilities: stats.total_vulnerabilities_found,
    averageRisk: Math.round(stats.average_risk_score),
    activeScans: stats.processing_scans
  } : {
    totalScans: 0,
    completedScans: 0,
    totalVulnerabilities: 0,
    averageRisk: 0,
    activeScans: 0
  };

  // Data for risk distribution chart
  const riskDistributionData = [
    { 
      name: 'Critical', 
      count: scans.filter(s => s.risk_score && s.risk_score >= 76).length,
      fill: '#DC2626'
    },
    { 
      name: 'High', 
      count: scans.filter(s => s.risk_score && s.risk_score >= 51 && s.risk_score < 76).length,
      fill: '#EA580C'
    },
    { 
      name: 'Medium', 
      count: scans.filter(s => s.risk_score && s.risk_score >= 26 && s.risk_score < 51).length,
      fill: '#D97706'
    },
    { 
      name: 'Low', 
      count: scans.filter(s => s.risk_score && s.risk_score < 26).length,
      fill: '#16A34A'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">
            PHANTOM Security AI
          </h1>
          <p className="text-gray-300">
            Autonomous vulnerability detection powered by artificial intelligence
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-400">Total Scans</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-white">{displayStats.totalScans}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-400">Completed</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-blue-400">{displayStats.completedScans}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-400">Vulnerabilities Found</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-red-500">{displayStats.totalVulnerabilities}</p>
            </CardContent>
          </Card>
          
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-400">Average Risk</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-3xl font-bold ${getRiskColor(displayStats.averageRisk)}`}>
                {displayStats.averageRisk}
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-gray-400">Active Scans</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold text-green-500">{displayStats.activeScans}</p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* New Scan */}
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">Initialize Security Scan</CardTitle>
              <CardDescription className="text-gray-400">
                Enter a domain or IP address to begin vulnerability assessment
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 mb-4">
                <Input
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  placeholder="example.com or 192.168.1.1"
                  className="flex-1 bg-slate-900 border-slate-600 text-white placeholder-gray-400"
                  onKeyPress={(e) => e.key === 'Enter' && !loading && startScan()}
                  disabled={loading}
                />
                <Button 
                  onClick={startScan}
                  disabled={loading || !target.trim()}
                  className="bg-purple-600 hover:bg-purple-700 disabled:bg-slate-600"
                >
                  {loading ? 'Scanning...' : 'Start Scan'}
                </Button>
              </div>
              
              {(loading || activeScanId) && (
                <div className="space-y-2">
                  <Progress value={progress} className="h-2" />
                  <div className="flex justify-between text-sm text-gray-400">
                    <span>{status || phase}</span>
                    <span>{progress}%</span>
                  </div>
                  {!isConnected && (
                    <p className="text-xs text-orange-400">
                      WebSocket {connectionStatus}...
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Risk Distribution Chart */}
          <Card className="bg-slate-800 border-slate-700">
            <CardHeader>
              <CardTitle className="text-white">Risk Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={riskDistributionData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1F2937', 
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6'
                    }} 
                  />
                  <Bar dataKey="count" fill="#8B5CF6" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Recent Scans */}
        <Card className="bg-slate-800 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white">Recent Scans</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {scans.length === 0 ? (
                <p className="text-gray-400 text-center py-8">No scans yet. Start your first scan above.</p>
              ) : (
                scans.slice(0, 10).map((scan) => (
                  <div key={scan.id} className="flex items-center justify-between p-4 bg-slate-900 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-1">
                        <p className="text-white font-medium">{scan.target}</p>
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          scan.status === 'completed' ? 'bg-green-900 text-green-300' :
                          scan.status === 'processing' ? 'bg-blue-900 text-blue-300' :
                          scan.status === 'failed' ? 'bg-red-900 text-red-300' :
                          'bg-gray-900 text-gray-300'
                        }`}>
                          {scan.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400">
                        {new Date(scan.created_at).toLocaleString()}
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-6">
                      {scan.status === 'completed' && (
                        <>
                          <div className="text-center">
                            <p className="text-xs text-gray-400">Risk Score</p>
                            <p className={`text-xl font-bold ${getRiskColor(scan.risk_score)}`}>
                              {scan.risk_score}/100
                            </p>
                            <p className={`text-xs ${getRiskColor(scan.risk_score)}`}>
                              {getRiskLevel(scan.risk_score)}
                            </p>
                          </div>
                          
                          <div className="text-center">
                            <p className="text-xs text-gray-400">Vulnerabilities</p>
                            <p className="text-xl font-bold text-red-400">
                              {scan.vulnerability_count}
                            </p>
                          </div>
                          
                          <div className="space-x-2">
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="border-slate-600 text-slate-300 hover:bg-slate-700"
                              onClick={() => handleViewReport(scan.id)}
                            >
                              View Report
                            </Button>
                            <Button 
                              variant="outline" 
                              size="sm" 
                              className="border-slate-600 text-slate-300 hover:bg-slate-700"
                              onClick={() => handleDownloadPDF(scan.id)}
                            >
                              Download PDF
                            </Button>
                          </div>
                        </>
                      )}
                      
                      {scan.status === 'processing' && (
                        <div className="flex items-center gap-2">
                          <div className="animate-spin h-5 w-5 border-2 border-purple-500 rounded-full border-t-transparent"></div>
                          <span className="text-purple-400">Processing...</span>
                        </div>
                      )}
                      
                      {scan.status === 'failed' && (
                        <div className="space-x-2">
                          <span className="text-red-400">Failed</span>
                          <Button variant="outline" size="sm" className="border-slate-600 text-slate-300 hover:bg-slate-700">
                            Retry
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}