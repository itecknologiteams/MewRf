package com.util;

import android.annotation.SuppressLint;
import android.app.ActionBar;
import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.DialogInterface;
import android.content.DialogInterface.OnClickListener;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.graphics.drawable.Drawable;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.MediaPlayer;
import android.media.ToneGenerator;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Message;
import android.os.Vibrator;
import android.os.storage.StorageManager;
import android.util.Log;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;


import com.hopeland.pda.example.R;

import java.lang.reflect.Array;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@SuppressLint("HandlerLeak")
public class BaseActivity extends Activity {
	protected static final String TAG = "Example";
	private Toast _MyToast = null;

	protected static final int MSG_SHOW_WAIT = -1;
	protected static final int MSG_HIDE_WAIT = -2;
	protected static final int MSG_SHOW_TIP = -3;
	protected static final int MSG_SHOW_MSG = -4;
	protected static final int MSG_SHOW_CONFIRM = -5;
	protected static final int MSG_UPDATE_WAIT = -6;
	protected static final int MSG_SHOW_INPUT = -7;
	protected static final int MSG_SHOW_LONG_TIP = -8;

	protected static final int MSG_USER_BEG = 0;

	private ProgressDialog waitDialog = null;
	private Lock waitDialogLock = new Lock();
	private Handler handler = new Handler() {
		@Override
		public void handleMessage(Message msg) {
			switch (msg.what) {
				case MSG_SHOW_WAIT:
					doShowWaitDialog(null, (String) msg.obj);
					break;
				case MSG_UPDATE_WAIT:
					doUpdateWaitDialog(null, (String) msg.obj);
					break;
				case MSG_HIDE_WAIT:
					doHideWaitDialog();
					break;
				case MSG_SHOW_TIP:
					doShowTip((String) msg.obj, false);
					break;
				case MSG_SHOW_LONG_TIP:
					doShowTip((String) msg.obj, true);
					break;
				case MSG_SHOW_MSG:
					ShowMsgInfo msgInfo = (ShowMsgInfo) msg.obj;
					if (msgInfo != null) {
						doShowMsg(msgInfo.title, msgInfo.msg, msgInfo.listener);
					}
					break;
				case MSG_SHOW_CONFIRM:
					ShowConfimInfo confimInfo = (ShowConfimInfo) msg.obj;
					if (confimInfo != null) {
						doShowConfim(confimInfo.msg,
								confimInfo.okString, confimInfo.cancelString,
								confimInfo.okListener, confimInfo.cancelListener);
					}
					break;
				default:
					msgProcess(msg);
					break;
			}
		}
	};


	/****************************************************************
	 * 消息相关 相关
	 ***************************************************************/
	/**
	 * 消息处理
	 *
	 * @param msg
	 */
	protected void msgProcess(Message msg) {

	}

	/**
	 * 发送消息
	 *
	 * @param what
	 * @param obj
	 */
	protected void sendMessage(int what, Object obj) {
		handler.sendMessage(handler.obtainMessage(what, obj));
		try {
			Thread.sleep(10);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
	}

	/**
	 * 发送消息
	 *
	 * @param what
	 */
	protected void sendMessage(int what) {
		handler.sendMessage(handler.obtainMessage(what, null));
		try {
			Thread.sleep(10);
		} catch (InterruptedException e) {
			e.printStackTrace();
		}
	}

	/****************************************************************
	 * 提示信息 相关
	 ***************************************************************/

	/**
	 * 气泡提示
	 *
	 * @param msg
	 */
	protected void showTip(String msg) {
		sendMessage(MSG_SHOW_TIP, msg);
	}

	private synchronized void doShowTip(String msg, boolean isLong) {
		if (_MyToast == null) {
			_MyToast = Toast.makeText(BaseActivity.this, msg,
					isLong ? Toast.LENGTH_LONG : Toast.LENGTH_SHORT);
		} else {
			_MyToast.setText(msg);
		}
		_MyToast.show();
	}

	/**
	 * @param title
	 * @param info
	 */
	private void doShowWaitDialog(String title, String info) {
		synchronized (waitDialogLock) {
			try {
				if (waitDialog != null) {
					waitDialog.dismiss();
					waitDialog = null;
				}
			} catch (Exception e) {
			}
			waitDialog = ProgressDialog.show(this, title, info);
		}
	}

	private void doUpdateWaitDialog(String title, String info) {
		try {
			synchronized (waitDialogLock) {
				if (waitDialog != null) {
					waitDialog.setTitle(title);
					waitDialog.setMessage(info);
				}
			}
		} catch (Exception e) {

		}
	}

	private void doHideWaitDialog() {
		try {
			synchronized (waitDialogLock) {
				if (waitDialog != null) {
					waitDialog.dismiss();
					waitDialog = null;
				}
			}
		} catch (Exception e) {

		}
	}

	/**
	 * 显示等待信息
	 *
	 * @param msg 等待信息
	 */
	protected void showWait(String msg) {
		sendMessage(MSG_SHOW_WAIT, msg);
	}


	/**
	 * 更新等待信息
	 *
	 * @param msg 等待信息
	 */
	protected void updateWait(String msg) {
		sendMessage(MSG_UPDATE_WAIT, msg);
	}


	/**
	 * 隐藏等待信息
	 */
	protected void hideWait() {
		sendMessage(MSG_HIDE_WAIT, null);
	}

	protected class ShowMsgInfo {
		public String title;
		public String msg;
		public OnClickListener listener;
	}

	protected class ShowConfimInfo {
		public String msg;
		public String okString;
		public String cancelString;
		public OnClickListener okListener;
		public OnClickListener cancelListener;
	}

	public interface InputDialogInputFinishCallBack {
		void onInputDialogFinish(String text);
	}

	protected class ShowInputDialogInfo {
		public String title;
		public String info;
		public String edit;
		public InputDialogInputFinishCallBack callBack;
	}

	/**
	 * 显示提示消息
	 *
	 * @param msg
	 * @param listener
	 */
	private synchronized void doShowMsg(String title, String msg,
										OnClickListener listener) {
		new AlertDialog.Builder(this)
				.setIcon(android.R.drawable.ic_dialog_info).setTitle(title)
				.setMessage(msg)
				.setPositiveButton(getString(R.string.str_ok), listener)
				.setCancelable(false)
				.create().show();
	}

	/**
	 * 显示提示消息
	 *
	 * @param msg
	 * @param listener
	 */
	protected void showMsg(String title, String msg,
						   OnClickListener listener) {
		ShowMsgInfo info = new ShowMsgInfo();

		info.title = title;
		info.msg = msg;
		info.listener = listener;

		sendMessage(MSG_SHOW_MSG, info);
	}

	/**
	 * 显示提示消息
	 *
	 * @param msg
	 * @param listener
	 */
	protected void showMsg(int title, int msg,
						   OnClickListener listener) {
		showMsg(getString(title), getString(msg), listener);
	}

	/**
	 * 显示提示消息
	 *
	 * @param msg      提示消息
	 * @param listener 按键监听事件
	 */
	protected void showMsg(String msg, OnClickListener listener) {
		showMsg(null, msg, listener);
	}


	/**
	 * 显示提示消息
	 *
	 * @param msg 提示消息
	 */
	protected void showMsg(String msg) {
		showMsg(null, msg, null);
	}



	private synchronized void doShowConfim(String msg,
										   String okString, String cancelString,
										   OnClickListener okListener, OnClickListener cancelListener) {

		if (okString != null && !okString.isEmpty()) {
			okString = getString(R.string.str_ok);
		}

		if (cancelString != null && !cancelString.isEmpty()) {
			cancelString = getString(R.string.str_cancel);
		}

		new AlertDialog.Builder(this)
				.setIcon(android.R.drawable.ic_dialog_info).setTitle(getString(R.string.str_confirm))
				.setMessage(msg)
				.setPositiveButton(okString, okListener)
				.setNegativeButton(cancelString, cancelListener)
				.setCancelable(false)
				.create().show();
	}

	/**
	 * 显示对话框
	 *
	 * @param msg            对话框消息
	 * @param okString       确认按键显示名称
	 * @param cancelString   取消按键显示名称
	 * @param okListener     确认按键监听事件
	 * @param cancelListener 取消按键监听事件
	 */
	protected void showConfim(String msg,
							  String okString, String cancelString,
							  OnClickListener okListener, OnClickListener cancelListener) {
		ShowConfimInfo info = new ShowConfimInfo();

		info.msg = msg;
		info.okString = okString;
		info.cancelString = cancelString;
		info.okListener = okListener;
		info.cancelListener = cancelListener;

		sendMessage(MSG_SHOW_CONFIRM, info);
	}

	/**
	 * 显示对话框
	 *
	 * @param msg            对话框消息
	 * @param okListener     确认按键监听事件
	 * @param cancelListener 取消按键监听事件
	 */
	protected void showConfim(String msg, OnClickListener okListener,
							  OnClickListener cancelListener) {
		showConfim(msg, null, null, okListener, cancelListener);
	}


	/**
	 * 获取版本号
	 *
	 * @return 当前应用的版本号
	 */
	public String getVersion() {
		try {
			PackageManager manager = this.getPackageManager();
			PackageInfo info = manager.getPackageInfo(this.getPackageName(), 0);
			String version = info.versionName;
			return version;
		} catch (Exception e) {
			return null;
		}
	}

	private long lastClickTime;

	protected synchronized boolean isFastClick() {
		long time = System.currentTimeMillis();
		if (time - lastClickTime < 600) {
			return true;
		}
		lastClickTime = time;
		return false;
	}

	/****************************************************************
	 * 自定义标题栏 相关
	 ***************************************************************/

	/**
	 * 显示自定义的ActionBar
	 *
	 * @param title       标题
	 * @param subTitle    副标题
	 * @param left        左按钮
	 * @param right       右按钮
	 * @param left_icon   左按钮图标
	 * @param right_icon  有按钮图标
	 * @param leftListen  左按钮事件
	 * @param rightListen 右按钮事件
	 * @return 成功失败
	 */
	@SuppressLint("InflateParams")
	protected boolean showCustomBar(String title, String subTitle, String left,
									String right, int left_icon, int right_icon,
									View.OnClickListener leftListen, View.OnClickListener rightListen) {

		ActionBar actionBar = getActionBar();
		if (null == actionBar) {
			return false;
		}

		actionBar.setTitle("");
		actionBar.setDisplayShowHomeEnabled(false);

		LayoutInflater inflater = (LayoutInflater) getSystemService(LAYOUT_INFLATER_SERVICE);
		View custActionBar = inflater.inflate(R.layout.custom_action_bar, null);
		TextView tvTitle = (TextView) custActionBar
				.findViewById(R.id.actionBarTitle);
		TextView tvSubTitle = (TextView) custActionBar
				.findViewById(R.id.actionBarSubTitle);
		Button btnLeft = (Button) custActionBar
				.findViewById(R.id.actionBarLeft);
		Button btnRight = (Button) custActionBar
				.findViewById(R.id.actionBarRight);

		tvTitle.setText(title);
		if (subTitle != null) {
			tvSubTitle.setText(subTitle);
		} else {
			tvSubTitle.setVisibility(View.GONE);
		}

		if (left != null) {
			btnLeft.setText(" " + left);
		} else {
			btnLeft.setText("  ");
		}
		btnLeft.setOnClickListener(leftListen);
		if (left_icon > 0) {
			Drawable drawable = getResources().getDrawable(left_icon);
			drawable.setBounds(0, 0, drawable.getMinimumWidth(),
					drawable.getMinimumHeight());
			btnLeft.setCompoundDrawables(drawable, null, null, null);
		}

		if (right != null) {
			btnRight.setText(right + " ");
		} else {
			btnRight.setText("  ");
		}
		btnRight.setOnClickListener(rightListen);
		if (right_icon > 0) {
			Drawable drawable = getResources().getDrawable(right_icon);
			drawable.setBounds(0, 0, drawable.getMinimumWidth(),
					drawable.getMinimumHeight());
			btnRight.setCompoundDrawables(null, null, drawable, null);
		}

		if (null == left && left_icon <= 0) {
			btnLeft.setVisibility(View.GONE);
		}

		if (null == right && right_icon <= 0) {
			btnRight.setVisibility(View.GONE);
		}

		ActionBar.LayoutParams lp = new ActionBar.LayoutParams(
				ActionBar.LayoutParams.MATCH_PARENT,
				ActionBar.LayoutParams.MATCH_PARENT);
		actionBar.setDisplayShowCustomEnabled(true);
		actionBar.setCustomView(custActionBar, lp);

		return true;
	}

	/**
	 * 显示自定义的ActionBar
	 *
	 * @param title       标题
	 * @param left        左按钮
	 * @param right       右按钮
	 * @param left_icon   左按钮图标
	 * @param right_icon  有按钮图标
	 * @param leftListen  左按钮事件
	 * @param rightListen 右按钮事件
	 * @return 成功失败
	 */
	protected boolean showCustomBar(String title, String left, String right,
									int left_icon, int right_icon, View.OnClickListener leftListen,
									View.OnClickListener rightListen) {
		return showCustomBar(title, null, left, right, left_icon, right_icon,
				leftListen, rightListen);
	}

	/**
	 * 显示自动以的ActionBar
	 *
	 * @param title       标题
	 * @param left        左按钮
	 * @param right       右按钮 * @param leftListen 左按钮事件
	 * @param rightListen 右按钮事件
	 * @return 成功失败
	 */
	protected boolean showCustomBar(String title, String left, String right,
									View.OnClickListener leftListen, View.OnClickListener rightListen) {
		return showCustomBar(title, left, right, 0, 0, leftListen, rightListen);
	}

	/**
	 * 显示自动以的ActionBar
	 *
	 * @param title       标题
	 * @param subTitle    副标题
	 * @param left        左按钮
	 * @param right       右按钮
	 * @param leftListen  左按钮事件
	 * @param rightListen 右按钮事件
	 * @return 成功失败
	 */
	protected boolean showCustomBar(String title, String subTitle, String left,
									String right, View.OnClickListener leftListen,
									View.OnClickListener rightListen) {
		return showCustomBar(title, subTitle, left, right, 0, 0, leftListen,
				rightListen);
	}

	/****************************************************************
	 * 声音 相关
	 ***************************************************************/
	ToneGenerator toneGenerator;// = new ToneGenerator(AudioManager.STREAM_MUSIC,99);
	public static final int SUCESS_TONE = ToneGenerator.TONE_PROP_BEEP;
	public static final int ERROR_TONE = ToneGenerator.TONE_CDMA_EMERGENCY_RINGBACK;

	/**
	 * 播放声音
	 *
	 * @param toneType 参见ToneGenerator
	 */
	protected void playTone(final int toneType, final int timout) {
		try {
			new Thread() {
				@Override
				public void run() {
					try {
						sleep(timout);
						if (toneGenerator != null) {
							toneGenerator.stopTone();
						}
					} catch (InterruptedException e) {
					}
				}
			}.start();
			if (toneGenerator == null) {
				toneGenerator = new ToneGenerator(AudioManager.STREAM_MUSIC, 99);
			}
			toneGenerator.startTone(toneType);
		} catch (Exception e) {
		}
	}

	private MediaPlayer mShootMP;

	/**
	 * 播放声音
	 *
	 * @param toneType 参见ToneGenerator
	 */
	protected void playTone(final int toneType) {
		playTone(toneType, 1000);
		//toneGenerator.startTone(toneType);
	}

	/**
	 * 播放声音(来自文件)
	 */
	synchronized protected void playSound(String uriString) {
		AudioManager meng = (AudioManager) this.getSystemService(Context.AUDIO_SERVICE);
		int volume = meng.getStreamVolume(AudioManager.STREAM_NOTIFICATION);

		if (volume != 0) {
			if (mShootMP == null)
				mShootMP = MediaPlayer.create(this, Uri.parse(uriString));
			if (mShootMP != null)
				mShootMP.start();
		}
	}

	/**
	 * 模拟蜂鸣器叫
	 * @param hz
	 */
	public void beep(int hz, int ms) {
		/**
		 * 正弦波的高度
		 **/
		final int HEIGHT = 127;
		/**
		 * 2PI
		 **/
		final double TWOPI = 2 * 3.1415;

		final int SAMPLERATE = 44100;

		if (ms <= 0) {
			ms = 1;
		}
		if (hz <= 0) {
			hz = 1407;
		}

		int waveLen = SAMPLERATE / hz;
		int length = ms * SAMPLERATE / 1000;
		length = (length / waveLen) * waveLen;

		int bufferSize = AudioTrack.getMinBufferSize(SAMPLERATE,
				AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_8BIT);

		if ((length *2) > bufferSize) {
			bufferSize = length * 2;

		}
//		ms = (bufferSize * 1000 / SAMPLERATE) + 1;
		try {
			AudioTrack audioTrack = new AudioTrack(AudioManager.STREAM_MUSIC, SAMPLERATE,
					AudioFormat.CHANNEL_OUT_STEREO, // CHANNEL_CONFIGURATION_MONO,
					AudioFormat.ENCODING_PCM_8BIT, bufferSize, AudioTrack.MODE_STATIC);
			//生成正弦波
			byte[] wave = new byte[bufferSize];
			int i=0;
			for (; i < length; i++) {
				wave[i] = (byte) ((int)(HEIGHT * (1 -  Math.sin(TWOPI
						* ((i % waveLen) * 1.00 / waveLen)))) & 0xff);
			}

			for (; i < bufferSize; i++) {
				wave[i] = (byte) ((int)(HEIGHT * (1 - Math.sin(0)))& 0xff);
			}

			if (audioTrack != null) {

				audioTrack.write(wave, 0, bufferSize);
				audioTrack.play();
				Thread.sleep(ms*2);
				audioTrack.stop();
				audioTrack.release();
			}

		} catch (Exception e) {
			Log.e(TAG,"beep error:" + e.toString() + " \nlen:"+ length + "\nmin:"+bufferSize);
		}
	}
	/**
	 * 模拟蜂鸣器叫
	 */
	public void beep(int ms) {
		beep(1407, ms);
	}

	/**
	 * 模拟蜂鸣器叫
	 */
	public void beep() {
		beep(1407, 50);
	}

	public void beepWarnning() {
		beep(1407, 30);
		beep(1407, 30);
		beep(1407, 30);
	}

	/****************************************************************
	 * 震动 相关
	 ***************************************************************/
	private Vibrator vibrator = null;//(Vibrator)this.getSystemService(this.VIBRATOR_SERVICE);
	public static final int SHORT_VIBRATOR = 200;
	public static final int LONG_VIBRATOR = 1000;

	/**
	 * 震动
	 *
	 * @param milliseconds 震动时长
	 */
	protected void playVibrator(final int milliseconds) {
		if (null == vibrator) {
			vibrator = (Vibrator) this.getSystemService(Context.VIBRATOR_SERVICE);
		}
		vibrator.vibrate(milliseconds);
	}

	/**
	 * 震动
	 *
	 * @param pattern 震动参数 数组的a[0]表示静止的时间，a[1]代表的是震动的时间，然后数组的a[2]表示静止的时间，a[3]代表的是震动的时间……依次类推下去
	 * @param repeat  表示从哪里开始循环，比如这里的0表示这个数组在第一次循环完之后会从下标0开始循环到最后，这里的如果是-1表示不循环。
	 */
	protected void playVibrator(long[] pattern, int repeat) {
		if (null == vibrator) {
			vibrator = (Vibrator) this.getSystemService(Context.VIBRATOR_SERVICE);
		}
		vibrator.vibrate(pattern, repeat);
	}

	/**
	 * 取消震动
	 */
	protected void cancelVibrator() {
		if (vibrator != null) {
			vibrator.cancel();
		}
	}

//	private static PowerManager.WakeLock wakeLock = null;

	/****************************************************************
	 * 屏幕常亮 相关
	 ***************************************************************/
	public void keepScreenOn(boolean on) {
		if (on) {
//			if (null == wakeLock) {
//				PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
//				wakeLock = pm.newWakeLock(PowerManager.FULL_WAKE_LOCK | PowerManager.ON_AFTER_RELEASE, this.getClass().getName());
//				wakeLock.acquire();
//			}
//
			try {
				getWindow().setFlags(
						WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
						WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
			} catch (Exception ex) {
				//Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
			}
		} else {
//			if (wakeLock != null) {
//				wakeLock.release();
//				wakeLock = null;
//			}
			try {
				getWindow().setFlags(
						0,
						WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
			} catch (Exception ex) {
				//Log.d("Debug", "The initialization of abnormal:" + ex.getMessage());
			}
		}
	}

	/****************************************************************
	 * override 相关
	 ***************************************************************/
	@Override
	public void onBackPressed() {
		this.finish();
	}

	protected boolean __Exit = false;
	@Override
	protected void onDestroy() {
		keepScreenOn(false);
		cancelVibrator();
		super.onDestroy();

		__Exit = true;
	}

	@Override
	protected void onResume() {
		super.onResume();
		hideWait();
	}

	public boolean onKeyDown(int keyCode, KeyEvent event) {
		if (keyCode == KeyEvent.KEYCODE_HOME
				&& event.getRepeatCount() == 0) {
			return true;
		}
		return super.onKeyDown(keyCode, event);
	}

	public static final int FLAG_HOMEKEY_DISPATCHED = 0x80000000; //需要自己定义标志

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		this.getWindow().setFlags(FLAG_HOMEKEY_DISPATCHED, FLAG_HOMEKEY_DISPATCHED);//关键代码
	}

	/****************************************************************
	 * 界面辅助 相关
	 ***************************************************************/
	/**
	 * 获取显示宽度
	 *
	 * @return 像素
	 */
	protected int getWidth() {
		return getResources().getDisplayMetrics().widthPixels;
	}

	/**
	 * 获取显示高度
	 *
	 * @return 像素
	 */
	protected int getHeight() {
		return getResources().getDisplayMetrics().heightPixels;
	}

	/**
	 * 获取当先显示方向
	 *
	 * @return Configuration.ORIENTATION_LANDSCAPE or Configuration.ORIENTATION_PORTRAIT
	 */
	protected int getOrientation() {
		return getResources().getConfiguration().orientation;
	}

	/**
	 * 获取显示旋转角度
	 *
	 * @return Surface.ROTATION_0 or Surface.ROTATION_90 or Surface.ROTATION_180 or Surface.ROTATION_270
	 */
	protected int getRotation() {
		return getWindowManager().getDefaultDisplay()
				.getRotation();
	}

	/**
	 * 显示新界面
	 *
	 * @param cls    界面类
	 * @param intent 参数
	 */
	protected void showActivity(Class<?> cls, Intent intent) {
		if (intent == null) {
			intent = new Intent();
		}
		intent.setClass(this, cls);
		startActivity(intent);
	}

	/**
	 * 显示新界面
	 *
	 * @param cls 界面类
	 */
	protected void showActivity(Class<?> cls) {
		showActivity(cls, null);
	}

	/**
	 * 显示新界面并等待结果
	 *
	 * @param cls         界面类
	 * @param intent      参数
	 * @param requestCode 请求代码
	 */
	protected void showActivityForResult(Class<?> cls, Intent intent, int requestCode) {
		if (intent == null) {
			intent = new Intent();
		}
		intent.setClass(this, cls);
		startActivityForResult(intent, requestCode);
	}

	/**
	 * 显示新界面并等待结果
	 *
	 * @param cls         界面类
	 * @param requestCode 请求代码
	 */
	protected void showActivityForResult(Class<?> cls, int requestCode) {
		showActivityForResult(cls, null, requestCode);
	}

	/**
	 * 关闭界面并返回结果
	 *
	 * @param result 结果
	 * @param data   结果数据
	 */
	protected void hideActivityWithResult(int result, Intent data) {
		setResult(result, data);
		finish();
	}

	/**
	 * 关闭界面并返回结果
	 *
	 * @param result 结果
	 */
	protected void hideActivityWithResult(int result) {
		setResult(result);
		finish();
	}

	/**
	 * 进入全屏
	 */
	protected void enterFullScreen() {
		Window _window = getWindow();

		requestWindowFeature(Window.FEATURE_NO_TITLE);
		//全屏
		_window.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
				WindowManager.LayoutParams.FLAG_FULLSCREEN);

		WindowManager.LayoutParams params = _window.getAttributes();
		params.systemUiVisibility = View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE;
		_window.setAttributes(params);
	}

	/**
	 * 隐藏标题
	 */
	protected void hideTitle() {
		requestWindowFeature(Window.FEATURE_NO_TITLE);
	}

	/**
	 * 隐藏导航（虚拟按键）
	 */
	protected void hideNavigation() {
		Window _window = getWindow();
		WindowManager.LayoutParams params = _window.getAttributes();
		params.systemUiVisibility = View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE;
		_window.setAttributes(params);
	}

	/****************************************************************
	 * 存储 相关
	 ***************************************************************/
	/**
	 * 获取可存储路径
	 *
	 * @param is_removale 是否为可移动设备
	 * @return 存储路径或null
	 */
	public String getStoragePath(boolean is_removale) {
		StorageManager mStorageManager = (StorageManager) getSystemService(Context.STORAGE_SERVICE);
		Class<?> storageVolumeClazz = null;
		try {
			storageVolumeClazz = Class.forName("android.os.storage.StorageVolume");
			Method getVolumeList = mStorageManager.getClass().getMethod("getVolumeList");
			Method getPath = storageVolumeClazz.getMethod("getPath");
			Method isRemovable = storageVolumeClazz.getMethod("isRemovable");
			Object result = getVolumeList.invoke(mStorageManager);
			final int length = Array.getLength(result);
			for (int i = 0; i < length; i++) {
				Object storageVolumeElement = Array.get(result, i);
				String path = (String) getPath.invoke(storageVolumeElement);
				boolean removable = (Boolean) isRemovable.invoke(storageVolumeElement);
				if (is_removale == removable) {
					return path;
				}
			}
		} catch (ClassNotFoundException e) {
			e.printStackTrace();
		} catch (InvocationTargetException e) {
			e.printStackTrace();
		} catch (NoSuchMethodException e) {
			e.printStackTrace();
		} catch (IllegalAccessException e) {
			e.printStackTrace();
		}
		return null;
	}

	/****************************************************************
	 * 通用函数 相关
	 ***************************************************************/
	public boolean checkHexInput(String strInput) {
		boolean rt = false;
		Pattern p = Pattern.compile("^[a-f,A-F,0-9]*$");
		Matcher m = p.matcher(strInput);
		rt = m.matches();
		return rt;
	}
}
